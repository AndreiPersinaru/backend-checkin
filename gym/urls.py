from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TrainingSessionViewSet,
    AthleteViewSet,
    CheckInViewSet,
    UserManagementViewSet,
    PhoneNumberViewSet,
    AppSettingsViewSet,
    AthletePaymentViewSet,
    health_check
)

router = DefaultRouter()
router.register(r'training-sessions', TrainingSessionViewSet, basename='trainingsession')
router.register(r'athletes', AthleteViewSet, basename='athlete')
router.register(r'checkins', CheckInViewSet, basename='checkin')
router.register(r'users', UserManagementViewSet, basename='user')
router.register(r'phone-numbers', PhoneNumberViewSet, basename='phonenumber')
router.register(r'app-settings', AppSettingsViewSet, basename='appsettings')
router.register(r'athlete-payments', AthletePaymentViewSet, basename='athletepayment')

urlpatterns = [
    path('', include(router.urls)),
    path('health/', health_check, name='health-check'),
]
