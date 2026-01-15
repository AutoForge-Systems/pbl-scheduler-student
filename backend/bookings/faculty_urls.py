"""Faculty-only URL endpoints.

Mounted at /api/v1/faculty/ in scheduler/urls.py.
"""

from django.urls import path

from .faculty_views import (
    FacultyMarkAbsentView,
    FacultyMarkCompletedView,
    FacultyCancelBookingView,
    FacultyAbsentStudentsView,
    FacultyAllowRebookingView,
    FacultyAllowRebookingForBookingView,
)

urlpatterns = [
    path('bookings/<uuid:booking_id>/mark-absent', FacultyMarkAbsentView.as_view(), name='faculty-mark-absent'),
    path('bookings/<uuid:booking_id>/mark-completed', FacultyMarkCompletedView.as_view(), name='faculty-mark-completed'),
    path('bookings/<uuid:booking_id>/cancel', FacultyCancelBookingView.as_view(), name='faculty-cancel-booking'),
    path('absent-students', FacultyAbsentStudentsView.as_view(), name='faculty-absent-students'),
    path('absent/<uuid:booking_id>/allow-rebook/', FacultyAllowRebookingForBookingView.as_view(), name='faculty-allow-rebook-by-booking'),
    path('absent/allow-rebooking', FacultyAllowRebookingView.as_view(), name='faculty-allow-rebooking'),
]
