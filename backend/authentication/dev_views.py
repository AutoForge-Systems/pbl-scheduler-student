"""
Development-Only Authentication Views

WARNING: These views are intended for DEVELOPMENT ONLY.
They provide mock SSO functionality for testing when the real PBL system is unavailable.

Security:
- All endpoints check settings.DEBUG and return 403 if DEBUG=False
- No production usage is possible
- Same JWT flow as real SSO
"""
from django.conf import settings
from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import User
from core.assignment_models import StudentTeacherAssignment


class DevSSOLoginSerializer(serializers.Serializer):
    """Dev login request.

    Supports 2 modes:
    1) Login existing user by email
    2) Optionally create/update a user for quick real-time testing

    Security:
    - DEBUG must be True
    - ALLOW_DEV_LOGIN must be '1'
    - Optional DEV_LOGIN_SECRET can be required
    """

    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=['student', 'faculty'], required=False)
    name = serializers.CharField(required=False, allow_blank=True, max_length=255)
    pbl_user_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    create_if_missing = serializers.BooleanField(required=False, default=False)
    # Optional shared secret to prevent accidental exposure even in dev networks
    secret = serializers.CharField(required=False, allow_blank=True)


class DevSSOLoginView(APIView):
    """
    Development-Only SSO Login Endpoint.
    
    SIMPLIFIED FLOW:
    - User provides only email
    - Backend looks up existing user by email
    - If user exists: return their role and data
    - If user doesn't exist: return error (user must be pre-created)
    
    This simulates real SSO where user data comes from external system.
    
    POST /api/dev/sso-login
    
    Request body:
    {
        "email": "student@college.dev"
    }
    
    Response:
    {
        "access": "<jwt_access_token>",
        "refresh": "<jwt_refresh_token>",
        "user": {
            "id": "<uuid>",
            "email": "...",
            "name": "...",
            "role": "student|faculty",
            "pbl_user_id": "..."
        },
        "assignments": [...]  // Only for students
    }
    
    Security:
    - Returns HTTP 403 if DEBUG=False (production)
    - Uses same JWT generation as real SSO
    """
    permission_classes = [AllowAny]

    def post(self, request):
        # CRITICAL SECURITY CHECK: Only allow in development
        if not settings.DEBUG:
            return Response(
                {
                    'error': 'Development endpoint disabled',
                    'detail': 'This endpoint is only available in development mode.'
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if str(getattr(settings, 'ALLOW_DEV_LOGIN', '0')) != '1':
            return Response(
                {
                    'error': 'Development endpoint disabled',
                    'detail': 'Set ALLOW_DEV_LOGIN=1 to enable dev login.'
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate request data
        serializer = DevSSOLoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'Invalid request', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        email = serializer.validated_data['email']
        create_if_missing = bool(serializer.validated_data.get('create_if_missing'))

        configured_secret = (getattr(settings, 'DEV_LOGIN_SECRET', '') or '').strip()
        provided_secret = (serializer.validated_data.get('secret') or '').strip()
        if configured_secret and provided_secret != configured_secret:
            return Response(
                {
                    'error': 'Forbidden',
                    'detail': 'Invalid dev login secret.'
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        role = serializer.validated_data.get('role')
        name = (serializer.validated_data.get('name') or '').strip()
        pbl_user_id = (serializer.validated_data.get('pbl_user_id') or '').strip()

        user = User.objects.filter(email=email).first()
        if user is None:
            if not create_if_missing:
                return Response(
                    {
                        'error': 'User not found',
                        'detail': (
                            f'No user with email "{email}" exists. '
                            'Either pre-create the user or pass create_if_missing=true.'
                        )
                    },
                    status=status.HTTP_404_NOT_FOUND,
                )

            if not role:
                return Response(
                    {'error': 'Invalid request', 'detail': 'role is required when create_if_missing=true'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user = User.objects.create_user(
                email=email,
                name=name or email.split('@')[0],
                role=role,
                pbl_user_id=pbl_user_id or None,
            )
        else:
            # Optional: update user fields for convenience
            update_fields = []
            if role and user.role != role:
                user.role = role
                update_fields.append('role')
            if name and user.name != name:
                user.name = name
                update_fields.append('name')
            if pbl_user_id and user.pbl_user_id != pbl_user_id:
                user.pbl_user_id = pbl_user_id
                update_fields.append('pbl_user_id')
            if update_fields:
                user.save(update_fields=update_fields)

        # Generate JWT tokens using SimpleJWT (same as real SSO)
        refresh = RefreshToken.for_user(user)
        access = refresh.access_token

        # Build response
        response_data = {
            'access': str(access),
            'refresh': str(refresh),
            'user': {
                'id': str(user.id),
                'email': user.email,
                'name': user.name,
                'role': user.role,
                'pbl_user_id': user.pbl_user_id
            }
        }
        
        # For students, include their assignments
        if user.role == 'student':
            assignments = StudentTeacherAssignment.objects.filter(student=user)
            response_data['assignments'] = [
                {
                    'subject': a.subject,
                    'teacher_id': a.teacher_external_id
                }
                for a in assignments
            ]

        return Response(response_data, status=status.HTTP_200_OK)


class DevStatusView(APIView):
    """
    Check if dev mode is enabled.
    
    GET /api/dev/status
    
    Returns:
    {
        "dev_mode": true/false,
        "message": "..."
    }
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'dev_mode': settings.DEBUG,
            'message': 'Development mode enabled' if settings.DEBUG else 'Production mode'
        })
