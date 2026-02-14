"""
Core Views
"""
import os
import json
import re
from django.db.models.functions import Lower
from django.core.cache import cache
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings

from .serializers import UserSerializer
from .pbl_external import get_student_external_profile, pbl_probe_endpoint


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

        mentor_emails: list[str] = []
        teacher_identifiers = StudentTeacherAssignment.get_assigned_teacher_ids(user)
        teacher_ids = [t for t in teacher_identifiers if t and '@' not in str(t)]
        teacher_emails = [str(t).strip() for t in teacher_identifiers if t and '@' in str(t)]

        if teacher_ids:
            mentor_emails.extend(
                list(
                    User.objects.filter(role='faculty', pbl_user_id__in=teacher_ids)
                    .exclude(email__isnull=True)
                    .exclude(email__exact='')
                    .values_list('email', flat=True)
                )
            )
        if teacher_emails:
            mentor_emails.extend(teacher_emails)

        # Always union with external PBL data.
        profile = get_student_external_profile(user.email)
        ext_emails = profile.get('mentor_emails') or []
        if isinstance(ext_emails, list):
            mentor_emails.extend(ext_emails)

        mentor_emails = [str(e).strip() for e in mentor_emails if e and str(e).strip()]
        seen = set()
        mentor_emails = [e for e in mentor_emails if not (e.lower() in seen or seen.add(e.lower()))]

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


class SSOPayloadDebugView(APIView):
    """Return the last cached SSO verify payload summary.

    This is used to diagnose partner payload differences in production without
    exposing secrets.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        email_norm = (getattr(user, 'email', '') or '').strip().lower()
        if not email_norm:
            return Response({'detail': 'No email on user'}, status=status.HTTP_400_BAD_REQUEST)

        data = cache.get(f"sso:last_verify_payload:{email_norm}")
        return Response({
            'email': user.email,
            'has_payload': bool(data),
            'payload': data,
        })


class PBLProbeView(APIView):
    """Fetch a PBL API endpoint and return a safe summary for debugging.

    This is disabled by default in production. Enable explicitly with:
      ALLOW_PBL_DEBUG_PROBE=1

    Query params:
      - path: required, e.g. /students
      - params: optional JSON object (string) to pass as query params
            - scan: optional comma-separated key fragments to scan for in the matched student slice
    """

    permission_classes = [IsAuthenticated]

    _PATH_RE = re.compile(r'^/[A-Za-z0-9/_\-]+$')

    def get(self, request):
        if not getattr(settings, 'ALLOW_PBL_DEBUG_PROBE', False):
            return Response(
                {'detail': 'PBL probe is disabled'},
                status=status.HTTP_403_FORBIDDEN,
            )

        path = (request.query_params.get('path') or '').strip()
        if not path:
            return Response({'detail': 'Missing path'}, status=status.HTTP_400_BAD_REQUEST)

        if len(path) > 160 or not self._PATH_RE.match(path):
            return Response(
                {'detail': 'Invalid path format'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        params_raw = (request.query_params.get('params') or '').strip()
        params = None
        if params_raw:
            try:
                parsed = json.loads(params_raw)
                if not isinstance(parsed, dict):
                    return Response({'detail': 'params must be a JSON object'}, status=status.HTTP_400_BAD_REQUEST)
                # Ensure all values are simple scalars for requests.
                params = {str(k): v for k, v in parsed.items()}
            except Exception:
                return Response({'detail': 'Invalid params JSON'}, status=status.HTTP_400_BAD_REQUEST)

        base = (request.query_params.get('base') or 'default').strip().lower()
        if base not in ('default', 'teams'):
            return Response({'detail': 'Invalid base'}, status=status.HTTP_400_BAD_REQUEST)

        scan_raw = (request.query_params.get('scan') or '').strip()
        if scan_raw:
            scan_terms = [s.strip() for s in scan_raw.split(',') if s and s.strip()]
        else:
            scan_terms = ['evaluator', 'eval', 'assessor', 'faculty', 'teacher', 'subject', 'course', 'slot']

        email = (getattr(request.user, 'email', '') or '').strip()
        result = pbl_probe_endpoint(path, email=email, params=params, base=base, scan_terms=scan_terms)
        return Response({
            'email': email,
            'path': path,
            'base': base,
            'params': params or {},
            'result': result,
        })
