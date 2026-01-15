"""
SSO Service for PBL Integration
Handles both Mock and Real SSO modes.
"""
import logging
import requests
from typing import Optional, Dict, Any
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken
from core.models import User

logger = logging.getLogger(__name__)


class SSOService:
    """
    Service for handling SSO token verification and user creation.
    Supports both Mock mode (development) and Real mode (production).
    """
    
    def __init__(self):
        self.mode = settings.SSO_MODE
        self.pbl_api_url = settings.PBL_API_URL
        self.pbl_api_key = settings.PBL_API_KEY
    
    def verify_token(self, sso_token: str) -> Optional[Dict[str, Any]]:
        """
        Verify SSO token and return user data.
        
        Args:
            sso_token: The SSO token from PBL redirect
            
        Returns:
            User data dict or None if verification fails
        """
        if self.mode == 'mock':
            return self._mock_verify(sso_token)
        else:
            return self._real_verify(sso_token)
    
    def _mock_verify(self, sso_token: str) -> Optional[Dict[str, Any]]:
        """
        Mock SSO verification for development.
        
        Token format: mock_<role>_<user_id>_<email>_<name>
        Example: mock_student_123_john@example.com_John Doe
        
        Or simplified: mock_student or mock_faculty (uses defaults)
        """
        if not sso_token.startswith('mock_'):
            logger.warning(f"Invalid mock token format: {sso_token}")
            return None
        
        parts = sso_token.split('_', 4)
        
        if len(parts) == 2:
            # Simplified mock token: mock_student or mock_faculty
            _, role = parts
            if role not in ['student', 'faculty']:
                return None
            
            return {
                'pbl_user_id': f'mock_{role}_001',
                'email': f'mock.{role}@example.com',
                'name': f'Mock {role.title()}',
                'role': role
            }
        
        elif len(parts) >= 5:
            # Full mock token: mock_role_id_email_name
            _, role, user_id, email, name = parts[0], parts[1], parts[2], parts[3], '_'.join(parts[4:])
            
            if role not in ['student', 'faculty']:
                return None
            
            return {
                'pbl_user_id': user_id,
                'email': email,
                'name': name,
                'role': role
            }
        
        return None
    
    def _real_verify(self, sso_token: str) -> Optional[Dict[str, Any]]:
        """
        Real SSO verification by calling PBL API.
        
        Expected PBL API response format:
        {
            "valid": true,
            "user": {
                "id": "uuid-or-string",
                "email": "user@example.com",
                "role": "student" | "faculty"
            }
        }
        """
        try:
            if not self.pbl_api_url or not self.pbl_api_key:
                logger.error('PBL_API_URL / PBL_API_KEY not configured for real SSO mode')
                return None

            base = self.pbl_api_url.rstrip('/')
            response = requests.get(
                f"{base}/auth/verify",
                params={'token': sso_token},
                headers={'x-api-key': self.pbl_api_key},
                timeout=10,
            )
            
            if response.status_code != 200:
                logger.warning(f"PBL SSO verification failed: {response.status_code}")
                return None
            
            data = response.json()

            if not data.get('valid'):
                logger.warning('PBL SSO verification returned invalid')
                return None

            user_data = data.get('user', {})

            # Validate required fields
            required_fields = ['id', 'email', 'role']
            if not all(field in user_data for field in required_fields):
                logger.warning('PBL SSO response missing required fields')
                return None

            # Validate role
            if user_data['role'] not in ['student', 'faculty']:
                logger.warning(f"Invalid role from PBL: {user_data['role']}")
                return None

            # Name is optional in some partner payloads; fall back safely
            name = user_data.get('name') or user_data['email'].split('@')[0]

            return {
                'pbl_user_id': str(user_data['id']),
                'email': user_data['email'],
                'name': name,
                'role': user_data['role'],
            }
            
        except requests.RequestException as e:
            logger.error(f"Error calling PBL API: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing PBL response: {e}")
            return None
    
    def get_or_create_user(self, user_data: Dict[str, Any]) -> User:
        """
        Get existing user or create new one based on SSO data.
        Updates user info if it has changed.
        
        Args:
            user_data: Dict with pbl_user_id, email, name, role
            
        Returns:
            User instance
        """
        user, created = User.objects.update_or_create(
            email=user_data['email'],
            defaults={
                'name': user_data['name'],
                'role': user_data['role'],
                'pbl_user_id': user_data['pbl_user_id'],
                'is_active': True
            }
        )
        
        if created:
            logger.info(f"Created new user: {user.email} ({user.role})")
        else:
            logger.info(f"Updated existing user: {user.email}")
        
        return user
    
    def generate_tokens(self, user: User) -> Dict[str, str]:
        """
        Generate JWT tokens for the user.
        
        Args:
            user: User instance
            
        Returns:
            Dict with access and refresh tokens
        """
        refresh = RefreshToken.for_user(user)
        
        # Add custom claims
        refresh['email'] = user.email
        refresh['role'] = user.role
        refresh['name'] = user.name
        
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }


# Singleton instance
sso_service = SSOService()
