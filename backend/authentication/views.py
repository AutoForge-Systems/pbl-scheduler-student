"""
Authentication Views
"""
import logging
from django.conf import settings
from django.http import HttpResponseRedirect
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from urllib.parse import urlencode
from django.db import DatabaseError

from .sso_service import sso_service
from .serializers import SSOTokenSerializer
from core.serializers import UserSerializer


logger = logging.getLogger(__name__)


class SSOEntryView(APIView):
    """
    SSO Entry Point - Handles redirect from PBL platform.
    
    Flow:
    1. PBL redirects user to: /api/v1/auth/sso?token=<sso_token>
    2. Backend verifies token with PBL (or uses mock in dev)
    3. Backend creates/updates local user
    4. Backend generates JWT tokens
    5. Redirects to appropriate frontend with tokens
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Handle SSO redirect from PBL."""
        sso_token = (
            request.query_params.get('token')
            or request.query_params.get('sso_token')
            or request.query_params.get('ssoToken')
        )
        
        if not sso_token:
            return Response(
                {'error': 'Missing SSO token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify token
        user_data = sso_service.verify_token(sso_token)
        
        if not user_data:
            return Response(
                {'error': 'Invalid or expired SSO token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get or create user + generate JWT (may raise DB errors)
        try:
            user = sso_service.get_or_create_user(user_data)
            tokens = sso_service.generate_tokens(user)
        except DatabaseError as exc:
            logger.exception('SSOEntryView DB error during login: %s', exc)
            return Response(
                {'error': 'Service unavailable. Database error during SSO login.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Audit log (safe): do NOT log tokens.
        logger.info('SSOEntryView login success user_id=%s email=%s role=%s', user.id, user.email, user.role)
        
        # Determine redirect URL based on role
        if user.role == 'student':
            frontend_url = settings.STUDENT_FRONTEND_URL
        else:
            frontend_url = settings.FACULTY_FRONTEND_URL
        
        # Build redirect URL with tokens
        params = urlencode({
            'access': tokens['access'],
            'refresh': tokens['refresh']
        })
        redirect_url = f"{frontend_url}/auth/callback?{params}"
        
        return HttpResponseRedirect(redirect_url)


class SSOVerifyView(APIView):
    """
    SSO Verification API - For programmatic token verification.
    Returns JSON instead of redirect.
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Verify SSO token and return JWT tokens."""
        serializer = SSOTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        sso_token = serializer.validated_data['token']
        
        # Verify token
        user_data = sso_service.verify_token(sso_token)
        
        if not user_data:
            return Response(
                {'error': 'Invalid or expired SSO token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get or create user + generate JWT (may raise DB errors)
        try:
            user = sso_service.get_or_create_user(user_data)
            tokens = sso_service.generate_tokens(user)
        except DatabaseError as exc:
            logger.exception('SSOVerifyView DB error during verify: %s', exc)
            return Response(
                {'error': 'Service unavailable. Database error during SSO verify.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        logger.info('SSOVerifyView success user_id=%s email=%s role=%s', user.id, user.email, user.role)
        
        # Determine redirect URL
        if user.role == 'student':
            redirect_url = settings.STUDENT_FRONTEND_URL
        else:
            redirect_url = settings.FACULTY_FRONTEND_URL
        
        return Response({
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': UserSerializer(user).data,
            'redirect_url': redirect_url
        })


class SSOLoginView(APIView):
    """Frontend-friendly SSO login endpoint.

    Accepts an SSO token via querystring and returns JWT tokens as JSON.
    This keeps the PBL API key on the server and avoids putting JWTs in URLs.

    GET /api/v1/auth/sso-login?sso_token=<token>
    """

    permission_classes = [AllowAny]

    def get(self, request):
        sso_token = (
            request.query_params.get('sso_token')
            or request.query_params.get('token')
            or request.query_params.get('ssoToken')
        )
        if not sso_token:
            return Response({'detail': 'Missing SSO token'}, status=status.HTTP_400_BAD_REQUEST)

        user_data = sso_service.verify_token(sso_token)
        if not user_data:
            return Response({'detail': 'Invalid or expired SSO token'}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            user = sso_service.get_or_create_user(user_data)
            tokens = sso_service.generate_tokens(user)
        except DatabaseError as exc:
            logger.exception('SSOLoginView DB error during login: %s', exc)
            return Response(
                {'detail': 'Service unavailable. Database error during SSO login.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as exc:
            # Catch-all: this endpoint is often the first hit in production; make failures debuggable.
            logger.exception('SSOLoginView unexpected error: %s', exc)
            return Response(
                {'detail': 'Unexpected error during SSO login.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        logger.info('SSOLoginView login success user_id=%s email=%s role=%s', user.id, user.email, user.role)
        return Response({
            'access': tokens['access'],
            'refresh': tokens['refresh'],
            'user': UserSerializer(user).data,
            'redirect_url': settings.STUDENT_FRONTEND_URL if user.role == 'student' else settings.FACULTY_FRONTEND_URL,
        }, status=status.HTTP_200_OK)


class MockSSOGenerateView(APIView):
    """
    Development-only endpoint to generate mock SSO tokens.
    Only available when SSO_MODE=mock
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Generate mock SSO URL for testing."""
        if settings.SSO_MODE != 'mock':
            return Response(
                {'error': 'Mock SSO is disabled in production'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        role = request.query_params.get('role', 'student')
        email = request.query_params.get('email', f'test.{role}@example.com')
        name = request.query_params.get('name', f'Test {role.title()}')
        user_id = request.query_params.get('user_id', f'{role}_001')
        
        if role not in ['student', 'faculty']:
            return Response(
                {'error': 'Invalid role. Must be student or faculty'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate mock token
        mock_token = f"mock_{role}_{user_id}_{email}_{name}"
        
        # Build SSO URL
        sso_url = request.build_absolute_uri(f'/api/v1/auth/sso?token={mock_token}')
        
        return Response({
            'message': 'Mock SSO token generated',
            'token': mock_token,
            'sso_url': sso_url,
            'instructions': 'Visit the sso_url to simulate PBL SSO redirect'
        })
