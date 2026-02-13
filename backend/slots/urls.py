"""
Slots URL Configuration
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FacultySlotViewSet, StudentSlotViewSet, SlotAvailabilitySummaryView, StudentSubjectAvailabilityView

router = DefaultRouter()
router.register(r'faculty', FacultySlotViewSet, basename='faculty-slots')
router.register(r'available', StudentSlotViewSet, basename='available-slots')

urlpatterns = [
    path('availability-summary/', SlotAvailabilitySummaryView.as_view(), name='slot-availability-summary'),
    path('student-availability/', StudentSubjectAvailabilityView.as_view(), name='student-availability'),
    path('', include(router.urls)),
]
