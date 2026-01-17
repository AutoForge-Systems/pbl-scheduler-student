"""
Core Views
"""
import os
from django.db.models.functions import Lower
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
        # These env vars are commonly available on Render. If missing, they will be null.
        git_commit = os.environ.get('RENDER_GIT_COMMIT')
        service_id = os.environ.get('RENDER_SERVICE_ID')
        instance_id = os.environ.get('RENDER_INSTANCE_ID')

        return Response({
            'status': 'healthy',
            'service': 'scheduler-api',
            'git_commit': git_commit,
            'render_service_id': service_id,
            'render_instance_id': instance_id,
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

        # Prefer local assignments (source of truth inside scheduler) so that
        # students with multiple subjects get *all* assigned teachers.
        from core.assignment_models import StudentTeacherAssignment
        from core.models import User

        mentor_emails = []
        teacher_ids = StudentTeacherAssignment.get_assigned_teacher_ids(user)
        if teacher_ids:
            mentor_emails = list(
                User.objects.filter(role='faculty', pbl_user_id__in=teacher_ids)
                .exclude(email__isnull=True)
                .exclude(email__exact='')
                .values_list('email', flat=True)
            )

        # Fallback to external PBL data if local assignments are missing.
        if not mentor_emails:
            profile = get_student_external_profile(user.email)
            mentor_emails = profile.get('mentor_emails') or []
            if not isinstance(mentor_emails, list):
                mentor_emails = []

        mentor_emails_norm = [str(e).strip() for e in mentor_emails if e and str(e).strip()]
        mentor_emails_lower = [e.lower() for e in mentor_emails_norm]

        # Resolve mentor names from local DB when possible.
        # If a mentor user doesn't exist locally yet, we still return the email with name=None.

        mentors_by_email_lower = {}
        if mentor_emails_lower:
            qs = (
                User.objects.filter(role='faculty')
                .annotate(email_l=Lower('email'))
                .filter(email_l__in=mentor_emails_lower)
                .only('id', 'name', 'email')
            )
            for m in qs:
                mentors_by_email_lower[(m.email or '').strip().lower()] = {
                    'id': str(m.id),
                    'name': m.name,
                    'email': m.email,
                }

        mentors = []
        for email in mentor_emails_norm:
            mentors.append(mentors_by_email_lower.get(email.lower()) or {'id': None, 'name': None, 'email': email})

        return Response({
            'mentor_emails': mentor_emails_norm,
            'mentors': mentors,
        })
