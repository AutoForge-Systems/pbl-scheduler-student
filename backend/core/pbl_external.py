import logging
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def _is_mock_mode() -> bool:
    return (getattr(settings, 'SSO_MODE', '') or '').lower() == 'mock'

def _mock_student_profile(email: str) -> Dict[str, Any]:
    """Local-only mock student profile.

    This enables dev/testing without a real PBL dependency.
    It derives mentor emails from local `StudentTeacherAssignment` rows.
    """
    from core.models import User
    from core.assignment_models import StudentTeacherAssignment

    email_norm = (email or '').strip().lower()
    profile: Dict[str, Any] = {
        'email': email,
        'mentor_emails': [],
        'raw': None,
    }

    if not email_norm:
        return profile

    student = User.objects.filter(email__iexact=email_norm, role='student').first()
    if not student:
        return profile

    teacher_ids = list(
        StudentTeacherAssignment.objects.filter(student=student)
        .values_list('teacher_external_id', flat=True)
        .distinct()
    )

    mentors_qs = User.objects.filter(role='faculty')
    if teacher_ids:
        mentors_qs = mentors_qs.filter(pbl_user_id__in=teacher_ids)

    mentor_emails = [u.email for u in mentors_qs if u.email]

    profile.update(
        {
            'mentor_emails': mentor_emails,
            'raw': {
                'email': student.email,
                'mentorEmails': mentor_emails,
            },
        }
    )

    return profile


def _headers() -> Dict[str, str]:
    api_key = getattr(settings, 'PBL_API_KEY', '')
    if not api_key:
        return {}

    # Partner spec requires `x-api-key`.
    return {
        'x-api-key': api_key,
    }


def _base_url() -> str:
    return (getattr(settings, 'PBL_API_URL', '') or '').rstrip('/')


def _get_json(path: str, *, params: Optional[Dict[str, Any]] = None, timeout: int = 10) -> Optional[Dict[str, Any]]:
    base = _base_url()
    if not base or not getattr(settings, 'PBL_API_KEY', None):
        logger.error('PBL_API_URL / PBL_API_KEY not configured')
        return None

    try:
        resp = requests.get(f"{base}{path}", headers=_headers(), params=params or {}, timeout=timeout)
        if resp.status_code != 200:
            body_preview = (resp.text or '').strip().replace('\n', ' ')
            if len(body_preview) > 300:
                body_preview = f"{body_preview[:300]}..."
            if resp.status_code in (401, 403):
                logger.error(
                    'PBL external API unauthorized: %s %s. Body: %s',
                    resp.status_code,
                    path,
                    body_preview,
                )
            else:
                logger.warning(
                    'PBL external API request failed: %s %s. Body: %s',
                    resp.status_code,
                    path,
                    body_preview,
                )
            return None
        return resp.json()
    except requests.RequestException as exc:
        logger.error('PBL external API request error: %s', exc)
        return None
    except ValueError as exc:
        logger.error('PBL external API JSON parse error: %s', exc)
        return None


def get_students() -> List[Dict[str, Any]]:
    if _is_mock_mode():
        from core.models import User
        from core.assignment_models import StudentTeacherAssignment

        students: List[Dict[str, Any]] = []
        for s in User.objects.filter(role='student'):
            teacher_ids = list(
                StudentTeacherAssignment.objects.filter(student=s)
                .values_list('teacher_external_id', flat=True)
                .distinct()
            )
            mentor_emails = list(
                User.objects.filter(role='faculty', pbl_user_id__in=teacher_ids)
                .values_list('email', flat=True)
            )
            students.append(
                {
                    'email': s.email,
                    'name': s.name,
                    'id': s.pbl_user_id,
                    'mentorEmails': mentor_emails,
                }
            )
        return students

    data = _get_json('/students') or {}
    students = data.get('students')
    return students if isinstance(students, list) else []


def get_faculty() -> List[Dict[str, Any]]:
    if _is_mock_mode():
        from core.models import User

        return [
            {
                'email': f.email,
                'name': f.name,
                'id': f.pbl_user_id,
            }
            for f in User.objects.filter(role='faculty')
        ]

    data = _get_json('/faculty') or {}
    faculty = data.get('faculty')
    return faculty if isinstance(faculty, list) else []


def get_student_external_profile(email: str) -> Dict[str, Any]:
    """Return mentor emails for the given student email.

    Output shape:
      {
        'email': str,
        'mentor_emails': [str, ...],
        'raw': {...} | None
      }
    """
    email_norm = (email or '').strip().lower()
    cache_key = f"pbl:student_profile:{email_norm}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    if _is_mock_mode():
        profile = _mock_student_profile(email)
        cache.set(cache_key, profile, 60)
        return profile

    profile: Dict[str, Any] = {
        'email': email,
        'mentor_emails': [],
        'raw': None,
    }

    if not email_norm:
        cache.set(cache_key, profile, 60)
        return profile

    students = get_students()
    match = None
    for s in students:
        if not isinstance(s, dict):
            continue
        s_email = (s.get('email') or '').strip().lower()
        if s_email == email_norm:
            match = s
            break

    if not match:
        cache.set(cache_key, profile, 60)
        return profile

    mentor_emails = match.get('mentorEmails') or match.get('mentor_emails') or []
    if isinstance(mentor_emails, list):
        mentor_emails = [str(x).strip() for x in mentor_emails if x and str(x).strip()]
    else:
        mentor_emails = []

    profile.update({
        'mentor_emails': mentor_emails,
        'raw': match,
    })

    # Token validity is ~5 minutes; profile changes are infrequent. Cache briefly.
    cache.set(cache_key, profile, 300)
    return profile
