"""
Core URL Configuration
"""
from django.urls import path
from .views import CurrentUserView, HealthCheckView, ExternalStudentProfileView, SSOPayloadDebugView, PBLProbeView

urlpatterns = [
    path('me/', CurrentUserView.as_view(), name='current-user'),
    path('me/external-profile/', ExternalStudentProfileView.as_view(), name='external-student-profile'),
    path('me/sso-debug/', SSOPayloadDebugView.as_view(), name='sso-payload-debug'),
    path('me/pbl-probe/', PBLProbeView.as_view(), name='pbl-probe'),
    path('health/', HealthCheckView.as_view(), name='health-check'),
]
