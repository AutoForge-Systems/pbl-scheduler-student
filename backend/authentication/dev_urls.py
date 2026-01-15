"""
Development-Only URL Configuration

These URLs are for development testing only.
All endpoints verify DEBUG=True before processing.
"""
from django.urls import path
from .dev_views import DevSSOLoginView, DevStatusView

urlpatterns = [
    path('sso-login/', DevSSOLoginView.as_view(), name='dev-sso-login'),
    path('status/', DevStatusView.as_view(), name='dev-status'),
]
