"""
Custom Permissions for Scheduler
"""
from rest_framework.permissions import BasePermission


class IsStudent(BasePermission):
    """Permission check for student role."""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'student'
        )


class IsFaculty(BasePermission):
    """Permission check for faculty role."""
    
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == 'faculty'
        )


class IsSlotOwner(BasePermission):
    """Permission check for slot ownership (faculty)."""
    
    def has_object_permission(self, request, view, obj):
        return obj.faculty_id == request.user.id


class IsBookingOwner(BasePermission):
    """Permission check for booking ownership (student)."""
    
    def has_object_permission(self, request, view, obj):
        return obj.student_id == request.user.id
