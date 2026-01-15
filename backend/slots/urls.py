"""
Slots URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FacultySlotViewSet, StudentSlotViewSet

router = DefaultRouter()
router.register(r'faculty', FacultySlotViewSet, basename='faculty-slots')
router.register(r'available', StudentSlotViewSet, basename='available-slots')

urlpatterns = [
    path('', include(router.urls)),
]
