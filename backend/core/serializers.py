"""
Core Serializers
"""
from rest_framework import serializers
from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    
    class Meta:
        model = User
        fields = ['id', 'email', 'name', 'role', 'pbl_user_id', 'university_roll_number', 'created_at', 'updated_at']
        read_only_fields = ['id', 'email', 'role', 'created_at', 'updated_at']


class UserMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for User - used in nested responses."""
    
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'pbl_user_id', 'university_roll_number']
        read_only_fields = fields
