from django.contrib import admin
from .models import TrainingSession, Athlete, CheckIn


@admin.register(TrainingSession)
class TrainingSessionAdmin(admin.ModelAdmin):
    list_display = ['name', 'frequency', 'weekday', 'date', 'start_time', 'end_time', 'active']
    list_filter = ['frequency', 'active', 'weekday']
    search_fields = ['name']


@admin.register(Athlete)
class AthleteAdmin(admin.ModelAdmin):
    list_display = ['name', 'created_at']
    search_fields = ['name']


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ['athlete', 'training_session', 'timestamp']
    list_filter = ['timestamp', 'training_session']
    search_fields = ['athlete__name', 'training_session__name']
    date_hierarchy = 'timestamp'
