from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TrainingSessionViewSet,
    AthleteViewSet,
    CheckInViewSet,
    UserManagementViewSet,
    health_check
)

router = DefaultRouter()
router.register(r'training-sessions', TrainingSessionViewSet, basename='trainingsession')
router.register(r'athletes', AthleteViewSet, basename='athlete')
router.register(r'checkins', CheckInViewSet, basename='checkin')
router.register(r'users', UserManagementViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
    path('health/', health_check, name='health-check'),
]
