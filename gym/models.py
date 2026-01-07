from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError


class TrainingSession(models.Model):
    """Model pentru sesiunile de antrenament"""
    FREQUENCY_CHOICES = [
        ('once', 'O singură dată'),
        ('weekly', 'Săptămânal'),
    ]
    
    WEEKDAY_CHOICES = [
        (0, 'Luni'),
        (1, 'Marți'),
        (2, 'Miercuri'),
        (3, 'Joi'),
        (4, 'Vineri'),
        (5, 'Sâmbătă'),
        (6, 'Duminică'),
    ]
    
    name = models.CharField(max_length=200, verbose_name="Nume antrenament")
    frequency = models.CharField(
        max_length=10, 
        choices=FREQUENCY_CHOICES,
        verbose_name="Frecvență"
    )
    
    # Pentru antrenamente one-time
    date = models.DateField(null=True, blank=True, verbose_name="Data")
    
    # Pentru antrenamente weekly
    weekday = models.IntegerField(
        null=True, 
        blank=True, 
        choices=WEEKDAY_CHOICES,
        verbose_name="Ziua săptămânii"
    )
    
    start_time = models.TimeField(verbose_name="Ora de început")
    end_time = models.TimeField(verbose_name="Ora de sfârșit")
    
    active = models.BooleanField(default=True, verbose_name="Activ")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Sesiune de antrenament"
        verbose_name_plural = "Sesiuni de antrenament"
        ordering = ['weekday', 'date', 'start_time']
    
    def __str__(self):
        if self.frequency == 'once':
            return f"{self.name} - {self.date} ({self.start_time}-{self.end_time})"
        else:
            weekday_name = dict(self.WEEKDAY_CHOICES)[self.weekday]
            return f"{self.name} - {weekday_name} ({self.start_time}-{self.end_time})"
    
    def is_valid_checkin_time(self):
        """Verifică dacă timpul curent este valid pentru check-in (±30 min)"""
        from datetime import datetime, timedelta
        
        now = timezone.localtime(timezone.now())
        current_time = now.time()
        current_date = now.date()
        current_weekday = now.weekday()
        
        # Verifică dacă antrenamentul este activ
        if not self.active:
            return False
        
        # Pentru antrenamente one-time
        if self.frequency == 'once':
            if self.date != current_date:
                return False
        
        # Pentru antrenamente weekly
        elif self.frequency == 'weekly':
            if self.weekday != current_weekday:
                return False
        
        # Calculează fereastra de check-in (30 min înainte și după)
        start_checkin = (datetime.combine(current_date, self.start_time) - timedelta(minutes=30)).time()
        end_checkin = (datetime.combine(current_date, self.end_time) + timedelta(minutes=30)).time()
        
        return start_checkin <= current_time <= end_checkin


class Athlete(models.Model):
    """Model pentru sportivi"""
    
    # Validator pentru număr de telefon românesc
    phone_regex = RegexValidator(
        regex=r'^07\d{8}$',
        message="Numărul de telefon trebuie să fie format din 10 cifre și să înceapă cu 07 (ex: 0712345678)"
    )
    
    name = models.CharField(max_length=200, verbose_name="Nume")
    phone_number = models.CharField(
        max_length=10, 
        unique=True, 
        validators=[phone_regex],
        verbose_name="Număr de telefon",
        help_text="Format: 07XXXXXXXX (10 cifre)"
    )
    subscription_active = models.BooleanField(default=True, verbose_name="Abonament lunar activ")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Sportiv"
        verbose_name_plural = "Sportivi"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.phone_number})"
    
    def get_checkins_for_month(self, year, month):
        """Returnează numărul de check-in-uri pentru o lună specificată"""
        return self.checkins.filter(
            timestamp__year=year,
            timestamp__month=month
        ).count()


class CheckIn(models.Model):
    """Model pentru check-in-urile sportivilor"""
    athlete = models.ForeignKey(
        Athlete, 
        on_delete=models.CASCADE, 
        related_name='checkins',
        verbose_name="Sportiv"
    )
    training_session = models.ForeignKey(
        TrainingSession, 
        on_delete=models.CASCADE, 
        related_name='checkins',
        verbose_name="Sesiune antrenament"
    )
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Ora check-in")
    checkin_date = models.DateField(auto_now_add=True, verbose_name="Data check-in")
    
    class Meta:
        verbose_name = "Check-in"
        verbose_name_plural = "Check-in-uri"
        ordering = ['-timestamp']
        # Un sportiv poate face check-in o singură dată la un training session într-o zi
        constraints = [
            models.UniqueConstraint(
                fields=['athlete', 'training_session', 'checkin_date'],
                name='unique_athlete_session_date'
            )
        ]
    
    def __str__(self):
        return f"{self.athlete.name} - {self.training_session.name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
