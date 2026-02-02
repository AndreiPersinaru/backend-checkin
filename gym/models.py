from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
import random
import string


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
    
    name = models.CharField(max_length=200, verbose_name="Nume")
    pin = models.CharField(
        max_length=6, 
        unique=True,
        null=True,
        blank=True,
        verbose_name="PIN (6 cifre)",
        help_text="PIN unic de 6 cifre pentru verificare"
    )
    subscription_active = models.BooleanField(default=True, verbose_name="Abonament lunar activ")
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Legacy field - pentru migrare graduală, va deveni deprecated
    phone_number = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        verbose_name="Număr de telefon (legacy)",
        help_text="Nu mai este folosit, doar pentru migrare"
    )
    
    class Meta:
        verbose_name = "Sportiv"
        verbose_name_plural = "Sportivi"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} (PIN: {self.pin})"
    
    def get_checkins_for_month(self, year, month):
        """Returnează numărul de check-in-uri pentru o lună specificată"""
        return self.checkins.filter(
            timestamp__year=year,
            timestamp__month=month
        ).count()


class PhoneNumber(models.Model):
    """Model pentru numere de telefon"""
    
    phone_regex = RegexValidator(
        regex=r'^07\d{8}$',
        message="Numărul de telefon trebuie să fie format din 10 cifre și să înceapă cu 07 (ex: 0712345678)"
    )
    
    phone_number = models.CharField(
        max_length=10, 
        unique=True, 
        validators=[phone_regex],
        verbose_name="Număr de telefon",
        help_text="Format: 07XXXXXXXX (10 cifre)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Număr de telefon"
        verbose_name_plural = "Numere de telefon"
        ordering = ['phone_number']
    
    def __str__(self):
        return self.phone_number


class PhoneAthlete(models.Model):
    """Model de legătură many-to-many între PhoneNumber și Athlete"""
    
    phone_number = models.ForeignKey(
        PhoneNumber,
        on_delete=models.CASCADE,
        related_name='athletes',
        verbose_name="Număr de telefon"
    )
    athlete = models.ForeignKey(
        Athlete,
        on_delete=models.CASCADE,
        related_name='phone_numbers',
        verbose_name="Sportiv"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name="Data verificării PIN")
    
    class Meta:
        unique_together = ('phone_number', 'athlete')
        verbose_name = "Asociere telefon-sportiv"
        verbose_name_plural = "Asocieri telefon-sportiv"
        ordering = ['phone_number', 'athlete']
    
    def __str__(self):
        return f"{self.phone_number} → {self.athlete.name}"
    
    @property
    def is_verified(self):
        return self.verified_at is not None


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
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Ora check-in")
    checkin_date = models.DateField(default=timezone.localdate, verbose_name="Data check-in")
    
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


class AppSettings(models.Model):
    """Model pentru setări generale ale aplicației"""
    
    subscription_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=75.00,
        verbose_name="Cost abonament lunar"
    )
    session_cost = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=20.00,
        verbose_name="Cost per sesiune"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Setări aplicație"
        verbose_name_plural = "Setări aplicație"
    
    def __str__(self):
        return "Setări globale"
    
    @classmethod
    def get_settings(cls):
        """Returnează singura instanță de setări (singleton)"""
        return cls.objects.first() or cls.objects.create()


class AthletePayment(models.Model):
    """Model pentru plăți ale sportivilor pe luni"""
    
    PAYMENT_CHOICES = [
        ('cash', 'Cash'),
        ('card', 'Card'),
    ]
    
    athlete = models.ForeignKey(
        Athlete, 
        on_delete=models.CASCADE, 
        related_name='payments',
        verbose_name="Sportiv"
    )
    year = models.IntegerField(verbose_name="An")
    month = models.IntegerField(verbose_name="Lună (1-12)")
    paid = models.BooleanField(default=False, verbose_name="Plătit")
    payment_method = models.CharField(
        max_length=10, 
        choices=PAYMENT_CHOICES, 
        null=True, 
        blank=True,
        verbose_name="Metoda de plată"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('athlete', 'year', 'month')
        verbose_name = "Plată sportiv"
        verbose_name_plural = "Plăți sportivi"
        ordering = ['-year', '-month', 'athlete']
    
    def __str__(self):
        status = "Plătit" if self.paid else "Neplătit"
        return f"{self.athlete.name} - {self.month}/{self.year} ({status})"
