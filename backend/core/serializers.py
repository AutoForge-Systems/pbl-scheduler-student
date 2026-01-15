"""
Core Serializers
"""
from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'role', 'created_at', 'updated_at']
        read_only_fields = ['id', 'email', 'role', 'created_at', 'updated_at']


class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for User - used in nested responses."""
    
    class Meta:
        model = User
        fields = ['id', 'name', 'email']
        read_only_fields = fields
