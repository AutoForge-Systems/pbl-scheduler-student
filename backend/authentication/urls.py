"""
Authentication URL Configuration
"""
from django.urls import path
from .views import SSOEntryView, SSOVerifyView, MockSSOGenerateView, SSOLoginView

urlpatterns = [
    path('sso/', SSOEntryView.as_view(), name='sso-entry'),
    path('sso/verify/', SSOVerifyView.as_view(), name='sso-verify'),
    path('sso-login/', SSOLoginView.as_view(), name='sso-login'),
    path('sso/mock/', MockSSOGenerateView.as_view(), name='mock-sso'),
]
