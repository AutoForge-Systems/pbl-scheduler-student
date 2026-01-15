"""
Core Views
"""
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .serializers import UserSerializer
from .pbl_external import get_student_external_profile


class CurrentUserView(APIView):
    """Get current authenticated user's profile."""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class HealthCheckView(APIView):
    """Health check endpoint for monitoring."""
    permission_classes = []
    
    def get(self, request):
        return Response({
            'status': 'healthy',
            'service': 'scheduler-api'
        })


class ExternalStudentProfileView(APIView):
    """Return student mentorEmails + groupId from external PBL API.

    This endpoint exists so the frontend can fetch mentorEmails/groupId without
    exposing the external API key.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if getattr(user, 'role', None) != 'student':
            return Response({'detail': 'Only students have an external profile'}, status=status.HTTP_403_FORBIDDEN)

        profile = get_student_external_profile(user.email)
        return Response({
            'mentor_emails': profile.get('mentor_emails') or [],
            'group_id': profile.get('group_id'),
        })
