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

    def _normalize_role(self, raw_user: Dict[str, Any]) -> Optional[str]:
        """Map partner role payloads to our internal roles.

        We only support 'student' and 'faculty' internally.
        Some PBL deployments return role='user' for students.
        """
        raw_role = (raw_user.get('role') or raw_user.get('type') or '').strip().lower()

        # Explicit faculty/mentor flags take priority.
        for key in ('is_faculty', 'isFaculty', 'is_teacher', 'isTeacher', 'is_mentor', 'isMentor'):
            val = raw_user.get(key)
            if val is True:
                return 'faculty'

        if raw_role in {'faculty', 'teacher', 'mentor', 'staff'}:
            return 'faculty'
        if raw_role in {'student', 'learner', 'user'}:
            return 'student'
        if not raw_role:
            # If role missing, default safely to student.
            return 'student'

        return None

    def _pbl_headers(self) -> Dict[str, str]:
        """Return headers for PBL API requests.

        Partner spec requires `x-api-key`.
        """
        headers: Dict[str, str] = {}
        if self.pbl_api_key:
            headers['x-api-key'] = self.pbl_api_key
        return headers
    
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
            verify_path = getattr(settings, 'PBL_SSO_VERIFY_PATH', '/auth/verify')
            if not verify_path.startswith('/'):
                verify_path = f"/{verify_path}"

            # Useful in production debugging; does not include token.
            logger.info('PBL SSO verify call: %s%s', base, verify_path)

            response = requests.get(
                f"{base}{verify_path}",
                params={'token': sso_token},
                headers=self._pbl_headers(),
                timeout=10,
            )
            
            if response.status_code != 200:
                # Do not log sensitive params (token). Response body is usually safe and helps debugging.
                body_preview = (response.text or '').strip().replace('\n', ' ')
                if len(body_preview) > 300:
                    body_preview = f"{body_preview[:300]}..."
                if response.status_code in (401, 403):
                    logger.error(
                        'PBL SSO verification unauthorized: %s (check PBL_API_KEY / auth scheme). Body: %s',
                        response.status_code,
                        body_preview,
                    )
                else:
                    logger.warning(
                        'PBL SSO verification failed: %s. Body: %s',
                        response.status_code,
                        body_preview,
                    )
                return None
            
            data = response.json()

            if not data.get('valid'):
                logger.warning('PBL SSO verification returned invalid')
                return None

            user_data = data.get('user')
            if not isinstance(user_data, dict) or not user_data:
                # Some partners return the user payload at top-level.
                user_data = data if isinstance(data, dict) else {}

            # Validate required fields (role can be inferred)
            required_fields = ['id', 'email']
            if not all(field in user_data for field in required_fields):
                logger.warning('PBL SSO response missing required fields')
                return None

            # Ensure required values are usable (avoid DB errors on blank/None email)
            email = (user_data.get('email') or '').strip()
            ext_id = (user_data.get('id') or '')
            if not email or not str(ext_id).strip():
                logger.warning('PBL SSO response has empty id/email')
                return None

            role = self._normalize_role(user_data)
            if role not in {'student', 'faculty'}:
                logger.warning('Invalid role from PBL: %s', user_data.get('role'))
                return None

            # Name is optional in some partner payloads; fall back safely
            name = user_data.get('name') or email.split('@')[0]

            return {
                'pbl_user_id': str(user_data['id']),
                'email': email,
                'name': name,
                'role': role,
                # Keep raw payload so we can extract optional assignment info
                # (subject/mentor mappings) during user creation.
                'raw_user': user_data,
                'raw': data,
            }
            
        except requests.RequestException as e:
            logger.error(f"Error calling PBL API: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Error parsing PBL response: {e}")
            return None

    def _sync_student_assignments(self, student: User, raw_payload: Any) -> None:
        """Upsert StudentTeacherAssignment rows from a partner SSO payload.

        Many PBL deployments include subject/mentor info in the SSO verify response,
        sometimes for the currently selected subject only. We upsert whatever we
        find and do NOT delete existing assignments (so we can accumulate over time).
        """
        if not isinstance(raw_payload, dict):
            return

        from core.assignment_models import StudentTeacherAssignment

        def norm_subject(value: Any) -> Optional[str]:
            s = (str(value).strip() if value is not None else '')
            return s or None

        def norm_email(value: Any) -> Optional[str]:
            s = (str(value).strip() if value is not None else '')
            return s or None

        def norm_id(value: Any) -> Optional[str]:
            s = (str(value).strip() if value is not None else '')
            return s or None

        def resolve_teacher_external_id(teacher_id: Any, teacher_email: Any) -> Optional[str]:
            tid = norm_id(teacher_id)
            if tid:
                return tid

            email = norm_email(teacher_email)
            if not email:
                return None

            # If we only have email, map to local faculty user to obtain PBL id.
            teacher = (
                User.objects.filter(role='faculty', email__iexact=email)
                .exclude(pbl_user_id__isnull=True)
                .exclude(pbl_user_id__exact='')
                .only('pbl_user_id')
                .first()
            )
            return teacher.pbl_user_id if teacher else None

        def upsert(subject: Any, teacher_id: Any = None, teacher_email: Any = None) -> None:
            subj = norm_subject(subject)
            if not subj:
                return
            ext_id = resolve_teacher_external_id(teacher_id, teacher_email)
            if not ext_id:
                return
            StudentTeacherAssignment.create_or_update_assignment(student, ext_id, subj)

        # 1) If payload contains a selected subject + mentor info at top-level
        upsert(
            raw_payload.get('subject')
            or raw_payload.get('selectedSubject')
            or raw_payload.get('currentSubject')
            or raw_payload.get('subjectName'),
            raw_payload.get('teacherId')
            or raw_payload.get('teacher_id')
            or raw_payload.get('teacherExternalId')
            or raw_payload.get('mentorId')
            or raw_payload.get('mentor_id')
            or raw_payload.get('facultyId'),
            raw_payload.get('teacherEmail')
            or raw_payload.get('teacher_email')
            or raw_payload.get('mentorEmail')
            or raw_payload.get('mentor_email'),
        )

        # 2) Parse lists of subject assignments if present
        for list_key in (
            'assignments',
            'subjects',
            'courses',
            'modules',
            'studentSubjects',
            'teacherAssignments',
        ):
            items = raw_payload.get(list_key)
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue

                subject = (
                    item.get('subject')
                    or item.get('subjectName')
                    or item.get('name')
                    or item.get('title')
                )

                teacher_id = (
                    item.get('teacher_external_id')
                    or item.get('teacherExternalId')
                    or item.get('teacherId')
                    or item.get('mentorId')
                    or item.get('mentor_id')
                    or item.get('facultyId')
                )
                teacher_email = (
                    item.get('teacherEmail')
                    or item.get('teacher_email')
                    or item.get('mentorEmail')
                    or item.get('mentor_email')
                )

                teacher_obj = item.get('teacher') or item.get('mentor')
                if isinstance(teacher_obj, dict):
                    teacher_id = teacher_id or teacher_obj.get('id') or teacher_obj.get('userId')
                    teacher_email = teacher_email or teacher_obj.get('email')

                upsert(subject, teacher_id, teacher_email)
    
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

        # Optional: sync student subject assignments if the SSO payload includes them.
        # Never fail login due to assignment parsing.
        if user.role == 'student':
            raw_payload = user_data.get('raw_user') or user_data.get('raw')
            try:
                self._sync_student_assignments(user, raw_payload)
            except Exception as exc:
                logger.warning('Failed to sync student assignments during SSO: %s', exc)
        
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
