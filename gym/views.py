from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime, date as date_cls
import calendar
from django.contrib.auth.models import User
from django.http import JsonResponse
from .models import (
    TrainingSession, Athlete, CheckIn,
    PhoneNumber, PhoneAthlete, AppSettings, AthletePayment
)
from .serializers import (
    TrainingSessionSerializer, 
    AthleteSerializer, 
    CheckInSerializer,
    CheckInCreateSerializer,
    MonthlyStatsSerializer,
    AthleteStatsSerializer,
    PhoneNumberSerializer,
    PhoneAthleteSerializer,
    AthleteSimpleSerializer,
    AppSettingsSerializer,
    AthletePaymentSerializer,
    PhoneCheckInRequestSerializer,
    PhoneAthleteListSerializer,
    NewPhoneAthleteAssociationSerializer
)
from .user_serializers import (
    UserSerializer,
    UserCreateSerializer,
    UserUpdateSerializer
)


# Health check endpoint pentru deployment
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Endpoint simplu pentru health checks - fără autentificare"""
    return JsonResponse({'status': 'ok'})


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

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def phones(self, request, pk=None):
        """Returnează numerele de telefon asociate sportivului"""
        athlete = self.get_object()
        phone_links = PhoneAthlete.objects.filter(athlete=athlete).select_related('phone_number')
        phones = [
            {
                'id': link.id,
                'phone_number': link.phone_number.phone_number,
                'verified_at': link.verified_at,
                'created_at': link.created_at,
            }
            for link in phone_links
        ]
        return Response({
            'athlete_id': athlete.id,
            'phones': phones
        })

    @action(detail=True, methods=['get', 'post'], permission_classes=[IsAuthenticated])
    def attendance(self, request, pk=None):
        """Gestionare prezențe pentru un sportiv (listare lunară + add/remove)"""
        athlete = self.get_object()

        if request.method == 'POST':
            session_id = request.data.get('training_session_id')
            date_str = request.data.get('date')
            present = request.data.get('present', True)

            if not session_id or not date_str:
                return Response({'error': 'training_session_id și date sunt obligatorii.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'error': 'Format dată invalid. Folosește YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                session = TrainingSession.objects.get(id=session_id)
            except TrainingSession.DoesNotExist:
                return Response({'error': 'Sesiunea de antrenament nu există.'}, status=status.HTTP_404_NOT_FOUND)

            existing = CheckIn.objects.filter(
                athlete=athlete,
                training_session=session,
                checkin_date=target_date
            ).first()

            if present:
                if existing:
                    return Response({'message': 'Prezența există deja.'})

                # setăm timestamp la ora de start a antrenamentului
                naive_dt = datetime.combine(target_date, session.start_time)
                aware_dt = timezone.make_aware(naive_dt) if timezone.is_naive(naive_dt) else naive_dt

                checkin = CheckIn.objects.create(
                    athlete=athlete,
                    training_session=session,
                    timestamp=aware_dt,
                    checkin_date=target_date
                )
                return Response({'message': 'Prezență adăugată.', 'checkin_id': checkin.id})

            # present=False => șterge prezența
            if existing:
                existing.delete()
                return Response({'message': 'Prezență ștearsă.'})
            return Response({'message': 'Prezența nu exista.'})

        # GET: listare prezențe pe lună
        try:
            year = int(request.query_params.get('year', timezone.now().year))
            month = int(request.query_params.get('month', timezone.now().month))
        except ValueError:
            return Response({'error': 'Year/Month invalid.'}, status=status.HTTP_400_BAD_REQUEST)

        if month < 1 or month > 12:
            return Response({'error': 'Month invalid.'}, status=status.HTTP_400_BAD_REQUEST)

        last_day = calendar.monthrange(year, month)[1]
        start_date = date_cls(year, month, 1)
        end_date = date_cls(year, month, last_day)

        # Check-ins pentru sportiv în lună
        checkins = CheckIn.objects.filter(
            athlete=athlete,
            checkin_date__range=(start_date, end_date)
        ).select_related('training_session')

        checkins_by_key = {
            (c.checkin_date.isoformat(), c.training_session_id): c
            for c in checkins
        }

        days = []

        for day in range(1, last_day + 1):
            current_date = date_cls(year, month, day)
            weekday = current_date.weekday()

            once_sessions = TrainingSession.objects.filter(
                frequency='once',
                date=current_date,
                active=True
            )
            weekly_sessions = TrainingSession.objects.filter(
                frequency='weekly',
                weekday=weekday,
                active=True
            )

            sessions = list(once_sessions) + list(weekly_sessions)

            if not sessions:
                continue

            sessions_payload = []
            for s in sessions:
                key = (current_date.isoformat(), s.id)
                checkin = checkins_by_key.get(key)
                sessions_payload.append({
                    'id': s.id,
                    'name': s.name,
                    'start_time': s.start_time.strftime('%H:%M'),
                    'end_time': s.end_time.strftime('%H:%M'),
                    'attended': checkin is not None,
                    'checkin_id': checkin.id if checkin else None
                })

            days.append({
                'date': current_date.isoformat(),
                'day': day,
                'sessions': sessions_payload
            })

        return Response({
            'athlete_id': athlete.id,
            'year': year,
            'month': month,
            'days': days
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


def health_check(request):
    """Endpoint pentru verificarea stării aplicației"""
    from django.http import JsonResponse
    return JsonResponse({'status': 'ok'})


# ============= NEW VIEWSETS FOR PHONE/ATHLETE WORKFLOW =============

class PhoneNumberViewSet(viewsets.ModelViewSet):
    """ViewSet pentru numere de telefon și asocieri cu sportivi"""
    queryset = PhoneNumber.objects.all()
    serializer_class = PhoneNumberSerializer
    pagination_class = None
    
    def get_permissions(self):
        # Acțiuni publice pentru check-in flow
        if self.action in ['list', 'retrieve', 'get_athletes', 'create_athlete', 'add_athlete', 'remove_athlete']:
            return [AllowAny()]
        return [IsAuthenticated()]
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def get_athletes(self, request):
        """
        POST /api/phone-numbers/get_athletes/
        Body: {"phone_number": "0712345678"}
        Response: {"phone_number": "...", "athletes": [{...}]}
        """
        serializer = PhoneCheckInRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        phone_number = serializer.validated_data['phone_number']
        
        # Găsește sau creează PhoneNumber
        phone_obj, created = PhoneNumber.objects.get_or_create(phone_number=phone_number)
        
        # Returnează sportivii asociați
        response_serializer = PhoneAthleteListSerializer(phone_obj)
        return Response(response_serializer.data)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def add_athlete(self, request):
        """
        POST /api/phone-numbers/add_athlete/
        Body: {"phone_number": "0712345678", "athlete_pin": "123456"}
        Asociază un sportiv existent (prin PIN) cu un număr de telefon
        """
        serializer = NewPhoneAthleteAssociationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_athlete = serializer.save()
        
        return Response(
            PhoneAthleteSerializer(phone_athlete).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def create_athlete(self, request):
        """
        POST /api/phone-numbers/create_athlete/
        Body: {"phone_number": "0712345678", "athlete_name": "Nume Sportiv"}
        Creează un sportiv nou și îl asociază cu numărul de telefon
        """
        phone_number = request.data.get('phone_number', '').strip()
        athlete_name = request.data.get('athlete_name', '').strip()
        
        # Validare
        phone_number = ''.join(filter(str.isdigit, phone_number))
        if len(phone_number) != 10 or not phone_number.startswith('07'):
            return Response(
                {'error': 'Număr de telefon invalid. Format: 07XXXXXXXX'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not athlete_name:
            return Response(
                {'error': 'Numele sportivului este obligatoriu.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verifică dacă nume este duplicat
        if Athlete.objects.filter(name__iexact=athlete_name).exists():
            return Response(
                {'error': f'Un sportiv cu numele "{athlete_name}" există deja în sistem.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generează PIN unic
        import random
        import string
        while True:
            pin = ''.join(random.choices(string.digits, k=6))
            if not Athlete.objects.filter(pin=pin).exists():
                break
        
        # Creează sportivul
        athlete = Athlete.objects.create(name=athlete_name, pin=pin)
        
        # Găsește sau creează PhoneNumber
        phone_obj, _ = PhoneNumber.objects.get_or_create(phone_number=phone_number)
        
        # Creează asocierea
        phone_athlete = PhoneAthlete.objects.create(
            phone_number=phone_obj,
            athlete=athlete,
            verified_at=timezone.now()
        )
        
        return Response(
            PhoneAthleteSerializer(phone_athlete).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.AllowAny])
    def remove_athlete(self, request):
        """
        POST /api/phone-numbers/remove_athlete/
        Body: {"phone_number": "0712345678", "athlete_id": 1}
        Șterge asocierea dintre un număr de telefon și un sportiv
        """
        phone_number = request.data.get('phone_number', '').strip()
        athlete_id = request.data.get('athlete_id')
        
        phone_number = ''.join(filter(str.isdigit, phone_number))
        if len(phone_number) != 10:
            return Response(
                {'error': 'Număr de telefon invalid.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            phone_obj = PhoneNumber.objects.get(phone_number=phone_number)
            athlete = Athlete.objects.get(id=athlete_id)
            phone_athlete = PhoneAthlete.objects.get(phone_number=phone_obj, athlete=athlete)
            phone_athlete.delete()
            
            return Response({'message': 'Sportivul a fost eliminat din asocieri.'})
        except (PhoneNumber.DoesNotExist, Athlete.DoesNotExist, PhoneAthlete.DoesNotExist):
            return Response(
                {'error': 'Asocierea nu există.'},
                status=status.HTTP_404_NOT_FOUND
            )


class AppSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet pentru setări aplicație"""
    queryset = AppSettings.objects.all()
    serializer_class = AppSettingsSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def current(self, request):
        """GET /api/app-settings/current/ - Returnează setările curente"""
        settings = AppSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)


class AthletePaymentViewSet(viewsets.ModelViewSet):
    """ViewSet pentru plăți sportivi"""
    queryset = AthletePayment.objects.all()
    serializer_class = AthletePaymentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    
    def get_queryset(self):
        queryset = super().get_queryset()
        year = self.request.query_params.get('year')
        month = self.request.query_params.get('month')
        athlete_id = self.request.query_params.get('athlete_id')
        
        if year:
            queryset = queryset.filter(year=int(year))
        if month:
            queryset = queryset.filter(month=int(month))
        if athlete_id:
            queryset = queryset.filter(athlete_id=int(athlete_id))
        
        return queryset
