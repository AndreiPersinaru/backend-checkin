from rest_framework import serializers
from .models import (
    TrainingSession, Athlete, CheckIn, 
    PhoneNumber, PhoneAthlete, AppSettings, AthletePayment
)
from django.utils import timezone
from datetime import timedelta


class TrainingSessionSerializer(serializers.ModelSerializer):
    weekday_display = serializers.CharField(source='get_weekday_display', read_only=True)
    frequency_display = serializers.CharField(source='get_frequency_display', read_only=True)
    
    class Meta:
        model = TrainingSession
        fields = [
            'id', 'name', 'frequency', 'frequency_display', 
            'date', 'weekday', 'weekday_display', 
            'start_time', 'end_time', 'active', 
            'created_at', 'updated_at'
        ]
    
    def validate(self, data):
        """Validare: antrenamentele once trebuie să aibă date, weekly trebuie să aibă weekday"""
        if data.get('frequency') == 'once' and not data.get('date'):
            raise serializers.ValidationError("Antrenamentele 'o singură dată' trebuie să aibă o dată specificată.")
        
        if data.get('frequency') == 'weekly' and data.get('weekday') is None:
            raise serializers.ValidationError("Antrenamentele săptămânale trebuie să aibă o zi a săptămânii specificată.")
        
        if data.get('start_time') >= data.get('end_time'):
            raise serializers.ValidationError("Ora de început trebuie să fie înainte de ora de sfârșit.")
        
        return data


class AthleteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Athlete
        fields = ['id', 'name', 'pin', 'subscription_active', 'created_at']


class CheckInSerializer(serializers.ModelSerializer):
    athlete_name = serializers.CharField(source='athlete.name', read_only=True)
    training_session_name = serializers.CharField(source='training_session.name', read_only=True)
    
    class Meta:
        model = CheckIn
        fields = [
            'id', 'athlete', 'athlete_name', 
            'training_session', 'training_session_name', 
            'timestamp'
        ]
        read_only_fields = ['timestamp']


class CheckInCreateSerializer(serializers.Serializer):
    """Serializer pentru crearea unui check-in prin număr de telefon și eventual nume sau athlete_id"""
    phone_number = serializers.CharField(max_length=10)
    athlete_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    athlete_id = serializers.IntegerField(required=False)
    
    def validate_phone_number(self, value):
        """Validează formatul numărului de telefon"""
        # Elimină orice caractere non-digit
        value = ''.join(filter(str.isdigit, value))
        
        if len(value) != 10:
            raise serializers.ValidationError("Numărul de telefon trebuie să aibă exact 10 cifre.")
        if not value.startswith('07'):
            raise serializers.ValidationError("Numărul de telefon trebuie să înceapă cu 07.")
        return value
    
    def validate(self, data):
        """Verifică dacă există un antrenament valid în acest moment"""
        now = timezone.localtime(timezone.now())
        current_time = now.time()
        current_date = now.date()
        current_weekday = now.weekday()
        
        # Găsește antrenamentul valid pentru momentul curent
        valid_sessions = []
        
        # Verifică antrenamente one-time
        one_time_sessions = TrainingSession.objects.filter(
            frequency='once',
            date=current_date,
            active=True
        )
        
        for session in one_time_sessions:
            if session.is_valid_checkin_time():
                valid_sessions.append(session)
        
        # Verifică antrenamente weekly
        weekly_sessions = TrainingSession.objects.filter(
            frequency='weekly',
            weekday=current_weekday,
            active=True
        )
        
        for session in weekly_sessions:
            if session.is_valid_checkin_time():
                valid_sessions.append(session)
        
        if not valid_sessions:
            raise serializers.ValidationError(
                "Nu există niciun antrenament activ în acest moment. "
                "Check-in-ul este permis doar cu 30 de minute înainte și după antrenament."
            )
        
        # Folosește primul antrenament valid găsit
        data['training_session'] = valid_sessions[0]
        
        # Dacă avem athlete_id, îl folosim direct
        if 'athlete_id' in data and data['athlete_id']:
            try:
                athlete = Athlete.objects.get(id=data['athlete_id'])
                data['athlete'] = athlete
                data['is_new_athlete'] = False
                return data
            except Athlete.DoesNotExist:
                raise serializers.ValidationError("Sportivul cu acest ID nu există.")
        
        # Verifică dacă atletul există deja (legacy flow cu phone_number)
        phone_number = data['phone_number']
        athlete = Athlete.objects.filter(phone_number=phone_number).first()
        
        if athlete:
            # Atletul există deja
            data['athlete'] = athlete
            data['is_new_athlete'] = False
        else:
            # Atletul nu există, trebuie să adauge nume
            if not data.get('athlete_name') or not data['athlete_name'].strip():
                raise serializers.ValidationError(
                    "Atletul cu acest număr de telefon nu există în sistem. "
                    "Te rog să completezi numele complet."
                )
            data['is_new_athlete'] = True
        
        return data
    
    def create(self, validated_data):
        phone_number = validated_data['phone_number']
        training_session = validated_data['training_session']
        
        if validated_data['is_new_athlete']:
            # Creează atletul nou
            athlete = Athlete.objects.create(
                name=validated_data['athlete_name'].strip(),
                phone_number=phone_number
            )
        else:
            athlete = validated_data['athlete']
        
        # Verifică dacă sportivul s-a mai înregistrat astăzi la acest antrenament
        today = timezone.localtime(timezone.now()).date()
        existing_checkin = CheckIn.objects.filter(
            athlete=athlete,
            training_session=training_session,
            checkin_date=today
        ).first()
        
        if existing_checkin:
            raise serializers.ValidationError(
                f"Te-ai înregistrat deja la acest antrenament astăzi la ora {existing_checkin.timestamp.strftime('%H:%M')}."
            )
        
        # Creează check-in
        checkin = CheckIn.objects.create(
            athlete=athlete,
            training_session=training_session
        )
        
        return checkin


class AthleteStatsSerializer(serializers.Serializer):
    """Serializer pentru statistici sportivi"""
    athlete_id = serializers.IntegerField()
    athlete_name = serializers.CharField()
    checkin_count = serializers.IntegerField()


class MonthlyStatsSerializer(serializers.Serializer):
    """Serializer pentru statistici lunare"""
    year = serializers.IntegerField()
    month = serializers.IntegerField()
    athletes = AthleteStatsSerializer(many=True)


# ============= NEW SERIALIZERS FOR PHONE/ATHLETE WORKFLOW =============

class PhoneNumberSerializer(serializers.ModelSerializer):
    class Meta:
        model = PhoneNumber
        fields = ['id', 'phone_number', 'created_at']


class PhoneAthleteSerializer(serializers.ModelSerializer):
    athlete_name = serializers.CharField(source='athlete.name', read_only=True)
    athlete_pin = serializers.CharField(source='athlete.pin', read_only=True)
    phone_number = serializers.CharField(source='phone_number.phone_number', read_only=True)
    
    class Meta:
        model = PhoneAthlete
        fields = ['id', 'phone_number', 'athlete', 'athlete_name', 'athlete_pin', 'created_at', 'verified_at']
        read_only_fields = ['created_at', 'verified_at']


class AthleteSimpleSerializer(serializers.ModelSerializer):
    """Serializer simplificat pentru Athlete cu PIN"""
    class Meta:
        model = Athlete
        fields = ['id', 'name', 'pin', 'subscription_active', 'created_at']


class AppSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AppSettings
        fields = ['id', 'subscription_cost', 'session_cost', 'updated_at']


class AthletePaymentSerializer(serializers.ModelSerializer):
    athlete_name = serializers.CharField(source='athlete.name', read_only=True)
    
    class Meta:
        model = AthletePayment
        fields = [
            'id', 'athlete', 'athlete_name', 
            'year', 'month', 'paid', 'payment_method', 
            'created_at', 'updated_at'
        ]


class PhoneCheckInRequestSerializer(serializers.Serializer):
    """Serializer pentru cererea inițială de check-in cu număr de telefon"""
    phone_number = serializers.CharField(max_length=10)
    
    def validate_phone_number(self, value):
        """Validează formatul numărului de telefon"""
        value = ''.join(filter(str.isdigit, value))
        if len(value) != 10:
            raise serializers.ValidationError("Numărul de telefon trebuie să aibă exact 10 cifre.")
        if not value.startswith('07'):
            raise serializers.ValidationError("Numărul de telefon trebuie să înceapă cu 07.")
        return value


class PhoneAthleteListSerializer(serializers.Serializer):
    """Response cu lista de sportivi asociați unui număr de telefon"""
    phone_number = serializers.CharField()
    athletes = PhoneAthleteSerializer(many=True, read_only=True, source='athletes.all')
    
    def to_representation(self, instance):
        """Convertim PhoneNumber instance în dict cu athletes"""
        return {
            'phone_number': instance.phone_number,
            'athletes': PhoneAthleteSerializer(instance.athletes.all(), many=True).data
        }


class NewPhoneAthleteAssociationSerializer(serializers.Serializer):
    """Serializer pentru asocierea unui noul sportiv cu un număr de telefon (cu PIN verificare)"""
    phone_number = serializers.CharField(max_length=10)
    athlete_pin = serializers.CharField(max_length=6)
    
    def validate_phone_number(self, value):
        value = ''.join(filter(str.isdigit, value))
        if len(value) != 10:
            raise serializers.ValidationError("Numărul de telefon trebuie să aibă exact 10 cifre.")
        if not value.startswith('07'):
            raise serializers.ValidationError("Numărul de telefon trebuie să înceapă cu 07.")
        return value
    
    def validate(self, data):
        phone_number = data['phone_number']
        athlete_pin = data['athlete_pin']
        
        # Verifică dacă atletul există cu PIN-ul dat
        try:
            athlete = Athlete.objects.get(pin=athlete_pin)
        except Athlete.DoesNotExist:
            raise serializers.ValidationError("PIN-ul introdus nu este valid.")
        
        # Verifică dacă telefonul există
        try:
            phone_obj = PhoneNumber.objects.get(phone_number=phone_number)
        except PhoneNumber.DoesNotExist:
            raise serializers.ValidationError("Numărul de telefon nu există.")
        
        # Verifică dacă asocierea deja există
        if PhoneAthlete.objects.filter(phone_number=phone_obj, athlete=athlete).exists():
            raise serializers.ValidationError("Sportivul este deja asociat cu acest număr de telefon.")
        
        data['phone_obj'] = phone_obj
        data['athlete'] = athlete
        return data
    
    def create(self, validated_data):
        phone_obj = validated_data['phone_obj']
        athlete = validated_data['athlete']
        
        phone_athlete = PhoneAthlete.objects.create(
            phone_number=phone_obj,
            athlete=athlete,
            verified_at=timezone.now()
        )
        return phone_athlete
