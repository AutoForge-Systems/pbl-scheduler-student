"""
Bookings URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StudentBookingViewSet, FacultyBookingViewSet

router = DefaultRouter()
router.register(r'student', StudentBookingViewSet, basename='student-bookings')
router.register(r'faculty', FacultyBookingViewSet, basename='faculty-bookings')

urlpatterns = [
    path('', include(router.urls)),
]
