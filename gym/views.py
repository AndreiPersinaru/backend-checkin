from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count, Q
from django.utils import timezone
from django.contrib.auth.models import User
from .models import TrainingSession, Athlete, CheckIn
from .serializers import (
    TrainingSessionSerializer, 
    AthleteSerializer, 
    CheckInSerializer,
    CheckInCreateSerializer,
    MonthlyStatsSerializer,
    AthleteStatsSerializer
)
from .user_serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer
)
from .user_serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer
)


class IsAdminUser(permissions.BasePermission):
    """
    Permite acces doar utilizatorilor admin (staff sau superuser)
    """
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser)


class UserManagementViewSet(viewsets.ModelViewSet):
    """
    ViewSet pentru gestionarea utilizatorilor (manageri).
    Doar adminii pot accesa aceste endpoint-uri.
    """
    queryset = User.objects.filter(is_superuser=False).order_by('-date_joined')
    permission_classes = [IsAdminUser]
    pagination_class = None
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        return UserSerializer
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Returnează informații despre utilizatorul curent"""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class TrainingSessionViewSet(viewsets.ModelViewSet):
    """
    ViewSet pentru gestionarea sesiunilor de antrenament.
    Doar managerii autentificați pot crea/edita/șterge.
    List, retrieve și current sunt publice.
    """
    queryset = TrainingSession.objects.all()
    serializer_class = TrainingSessionSerializer
    pagination_class = None  # Dezactivează paginarea
    
    def get_permissions(self):
        # GET (list, retrieve): AllowAny
        # POST, PUT, PATCH, DELETE: IsAuthenticated
        if self.request.method in ['GET']:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Returnează antrenamentul curent valid pentru check-in"""
        now = timezone.localtime(timezone.now())
        current_date = now.date()
        current_weekday = now.weekday()
        
        # Verifică antrenamente one-time
        one_time_sessions = TrainingSession.objects.filter(
            frequency='once',
            date=current_date,
            active=True
        )
        
        for session in one_time_sessions:
            if session.is_valid_checkin_time():
                serializer = self.get_serializer(session)
                return Response(serializer.data)
        
        # Verifică antrenamente weekly
        weekly_sessions = TrainingSession.objects.filter(
            frequency='weekly',
            weekday=current_weekday,
            active=True
        )
        
        for session in weekly_sessions:
            if session.is_valid_checkin_time():
                serializer = self.get_serializer(session)
                return Response(serializer.data)
        
        return Response(
            {'detail': 'Nu există antrenament activ în acest moment.'},
            status=status.HTTP_404_NOT_FOUND
        )


class AthleteViewSet(viewsets.ModelViewSet):
    """
    ViewSet pentru sportivi.
    GET: public (toată lumea poate vedea);
    PATCH: managers (autentificați) pot actualiza subscription_active.
    """
    queryset = Athlete.objects.all()
    serializer_class = AthleteSerializer
    pagination_class = None  # Dezactivează paginarea
    
    def get_permissions(self):
        # GET: public; PATCH/PUT: managers autentificați
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get_queryset(self):
        return Athlete.objects.all()
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def stats(self, request, pk=None):
        """Statistici pentru un sportiv anume"""
        athlete = self.get_object()
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))
        
        checkin_count = athlete.get_checkins_for_month(year, month)
        
        return Response({
            'athlete_id': athlete.id,
            'athlete_name': athlete.name,
            'phone_number': athlete.phone_number,
            'subscription_active': athlete.subscription_active,
            'year': year,
            'month': month,
            'checkin_count': checkin_count
        })


class CheckInViewSet(viewsets.ModelViewSet):
    """
    ViewSet pentru check-in-uri.
    """
    queryset = CheckIn.objects.all()
    pagination_class = None  # Dezactivează paginarea
    serializer_class = CheckInSerializer
    
    def get_permissions(self):
        # POST (create) este public, restul necesită autentificare
        if self.action == 'create':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CheckInCreateSerializer
        return CheckInSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        checkin = serializer.save()
        
        # Returnează serializer-ul normal pentru response
        response_serializer = CheckInSerializer(checkin)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def monthly_stats(self, request):
        """Statistici lunare pentru toți sportivii"""
        year = int(request.query_params.get('year', timezone.now().year))
        month = int(request.query_params.get('month', timezone.now().month))
        
        # Calculează statistici pentru fiecare sportiv
        athletes = Athlete.objects.all()
        stats = []
        
        for athlete in athletes:
            checkin_count = athlete.get_checkins_for_month(year, month)
            if checkin_count > 0:  # Include doar sportivii cu check-in-uri
                stats.append({
                    'athlete_id': athlete.id,
                    'athlete_name': athlete.name,
                    'phone_number': athlete.phone_number,
                    'subscription_active': athlete.subscription_active,
                    'checkin_count': checkin_count
                })
        
        # Sortează după numărul de check-in-uri (descrescător)
        stats.sort(key=lambda x: x['checkin_count'], reverse=True)
        
        return Response({
            'year': year,
            'month': month,
            'athletes': stats
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Endpoint pentru verificarea stării aplicației"""
    return Response({'status': 'ok'})
