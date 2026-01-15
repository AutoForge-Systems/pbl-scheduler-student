"""
URL configuration for scheduler project.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API v1
    path('api/v1/auth/', include('authentication.urls')),
    path('api/v1/slots/', include('slots.urls')),
    path('api/v1/bookings/', include('bookings.urls')),
    path('api/v1/faculty/', include('bookings.faculty_urls')),
    path('api/v1/users/', include('core.urls')),
    
    # JWT Token Refresh
    path('api/v1/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Development-only endpoints (protected by DEBUG check in views)
    path('api/dev/', include('authentication.dev_urls')),
]
