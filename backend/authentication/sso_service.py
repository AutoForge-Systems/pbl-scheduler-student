"""
SSO Service for PBL Integration
Handles both Mock and Real SSO modes.
"""
import logging
import requests
from typing import Optional, Dict, Any
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
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
                'university_roll_number': f'mock_{role}_roll_001' if role == 'student' else None,
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
                'university_roll_number': f'mock_student_roll_{user_id}' if role == 'student' else None,
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

            # Optional external field: university roll number
            roll = (
                user_data.get('universityRollNumber')
                or user_data.get('university_roll_number')
                or user_data.get('universityRollNo')
                or user_data.get('university_roll_no')
                or user_data.get('rollNumber')
                or user_data.get('roll_number')
                or user_data.get('universityRoll')
            )
            roll_s = str(roll).strip() if roll is not None else ''

            # Some partners keep student-only fields at top level; try full payload too.
            if not roll_s and isinstance(data, dict):
                roll2 = (
                    data.get('universityRollNumber')
                    or data.get('university_roll_number')
                    or data.get('universityRollNo')
                    or data.get('university_roll_no')
                    or data.get('rollNumber')
                    or data.get('roll_number')
                    or data.get('universityRoll')
                )
                roll_s = str(roll2).strip() if roll2 is not None else ''

            return {
                'pbl_user_id': str(user_data['id']),
                'email': email,
                'name': name,
                'role': role,
                'university_roll_number': roll_s or None,
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

        Many PBL deployments include subject/mentor info in the SSO verify response.
        Some include only the currently selected subject; others include a full
        subject->mentor snapshot.

        We always upsert what we can find. If we detect a full snapshot (2+ distinct
        subjects, matching our expected student load), we also prune assignments
        not present in the snapshot so old test mappings don't linger.
        """
        if not isinstance(raw_payload, dict):
            return

        # Some partners wrap everything under `user`.
        # We'll try both the full payload and the nested user dict.
        payloads = [raw_payload]
        nested_user = raw_payload.get('user')
        if isinstance(nested_user, dict):
            payloads.append(nested_user)

        from core.assignment_models import StudentTeacherAssignment

        found_pairs: set[tuple[str, str]] = set()

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
            # If the faculty user doesn't exist locally yet, still persist the mapping
            # using the email as a stable identifier. Downstream slot filtering
            # understands both PBL user IDs and emails.
            return teacher.pbl_user_id if teacher else email

        def upsert(subject: Any, teacher_id: Any = None, teacher_email: Any = None) -> None:
            subj = norm_subject(subject)
            if not subj:
                return
            ext_id = resolve_teacher_external_id(teacher_id, teacher_email)
            if not ext_id:
                return
            StudentTeacherAssignment.create_or_update_assignment(student, ext_id, subj)
            found_pairs.add((subj, ext_id))

        for p in payloads:
            # 1) If payload contains a selected subject + mentor info
            upsert(
                p.get('subject')
                or p.get('selectedSubject')
                or p.get('currentSubject')
                or p.get('subjectName'),
                p.get('teacherId')
                or p.get('teacher_id')
                or p.get('teacherExternalId')
                or p.get('mentorId')
                or p.get('mentor_id')
                or p.get('evaluatorId')
                or p.get('evaluator_id')
                or p.get('evaluatorExternalId')
                or p.get('facultyId'),
                p.get('teacherEmail')
                or p.get('teacher_email')
                or p.get('mentorEmail')
                or p.get('mentor_email')
                or p.get('evaluatorEmail')
                or p.get('evaluator_email'),
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
                items = p.get(list_key)
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
                        or item.get('evaluatorExternalId')
                        or item.get('evaluatorId')
                        or item.get('evaluator_id')
                        or item.get('facultyId')
                    )
                    teacher_email = (
                        item.get('teacherEmail')
                        or item.get('teacher_email')
                        or item.get('mentorEmail')
                        or item.get('mentor_email')
                        or item.get('evaluatorEmail')
                        or item.get('evaluator_email')
                    )

                    teacher_obj = item.get('teacher') or item.get('mentor') or item.get('evaluator')
                    if isinstance(teacher_obj, dict):
                        teacher_id = teacher_id or teacher_obj.get('id') or teacher_obj.get('userId')
                        teacher_email = teacher_email or teacher_obj.get('email')

                    upsert(subject, teacher_id, teacher_email)

                # If the partner payload appears to contain a full snapshot (2+ subjects),
                # prune any local assignments that are no longer present.
                subjects_found = {s for (s, _) in found_pairs}
                if len(subjects_found) >= 2:
                    StudentTeacherAssignment.objects.filter(student=student).exclude(subject__in=subjects_found).delete()

    def _cache_last_sso_payload_debug(self, email: str, raw_payload: Any) -> None:
        """Cache a safe summary of the last SSO verify payload for debugging."""
        email_norm = (email or '').strip().lower()
        if not email_norm or not isinstance(raw_payload, dict):
            return

        top_keys = sorted([str(k) for k in raw_payload.keys()])
        user_keys = []
        raw_user = raw_payload.get('user')
        if isinstance(raw_user, dict):
            user_keys = sorted([str(k) for k in raw_user.keys()])

        # Only keep a small subset of fields that help us understand mapping.
        candidates = {
            'subject': raw_payload.get('subject') or raw_payload.get('subjectName') or raw_payload.get('selectedSubject'),
            'mentorEmail': raw_payload.get('mentorEmail') or raw_payload.get('mentor_email'),
            'mentorEmails': raw_payload.get('mentorEmails') or raw_payload.get('mentor_emails'),
            'teacherEmail': raw_payload.get('teacherEmail') or raw_payload.get('teacher_email'),
            'teacherId': raw_payload.get('teacherId') or raw_payload.get('teacherExternalId') or raw_payload.get('facultyId'),
            'universityRollNumber': (
                raw_payload.get('universityRollNumber')
                or raw_payload.get('university_roll_number')
                or raw_payload.get('rollNumber')
                or raw_payload.get('roll_number')
            ),
        }

        cache.set(
            f"sso:last_verify_payload:{email_norm}",
            {
                'received_at': timezone.now().isoformat(),
                'top_keys': top_keys,
                'user_keys': user_keys,
                'candidates': candidates,
            },
            60 * 30,
        )
    
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
                'university_roll_number': user_data.get('university_roll_number'),
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
            # Prefer the full verify payload so we see any subject/mentor fields
            # that may exist outside the nested user object.
            raw_payload = user_data.get('raw') or user_data.get('raw_user')
            try:
                self._cache_last_sso_payload_debug(user.email, raw_payload)
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
