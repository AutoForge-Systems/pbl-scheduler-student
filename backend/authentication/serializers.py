"""
Authentication Serializers
"""
from rest_framework import serializers


class SSOTokenSerializer(serializers.Serializer):
    """Serializer for SSO token verification request."""
    token = serializers.CharField(required=True, help_text="SSO token from PBL redirect")


class AuthResponseSerializer(serializers.Serializer):
    """Serializer for authentication response."""
    access = serializers.CharField(help_text="JWT access token")
    refresh = serializers.CharField(help_text="JWT refresh token")
    user = serializers.DictField(help_text="User information")
    redirect_url = serializers.CharField(help_text="Frontend URL to redirect to")
