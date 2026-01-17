import logging
from typing import Any, Dict, List, Optional

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


def _uniq_emails(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        email = (v or '').strip()
        if not email:
            continue
        key = email.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(email)
    return out


def _extract_mentor_emails(raw_student: Dict[str, Any]) -> Dict[str, Any]:
    """Extract mentor emails from a raw PBL student payload.

    PBL partner payloads vary by deployment. This tries multiple shapes:
    - mentorEmails: [str] | str | {subject: [str]|str}
    - mentors: [{email, subject?}, ...]
    - subjects/assignments/courses: [{name/subject/title, mentorEmail/mentorEmails/mentor{email}}, ...]

    Returns:
      {
        'mentor_emails': [str, ...],
        'mentor_emails_by_subject': {subject: [str, ...]},
      }
    """

    mentor_emails: List[str] = []
    mentor_emails_by_subject: Dict[str, List[str]] = {}

    def add_email(email: Any, subject: Optional[str] = None) -> None:
        if email is None:
            return
        email_s = str(email).strip()
        if not email_s:
            return
        mentor_emails.append(email_s)
        if subject:
            subject_s = str(subject).strip()
            if subject_s:
                mentor_emails_by_subject.setdefault(subject_s, []).append(email_s)

    def add_emails(value: Any, subject: Optional[str] = None) -> None:
        if value is None:
            return
        if isinstance(value, list):
            for item in value:
                add_email(item, subject)
            return
        if isinstance(value, dict):
            # If it's a dict keyed by subject -> mentor email(s)
            for k, v in value.items():
                subj = str(k).strip() if k is not None else None
                add_emails(v, subj or subject)
            return
        # string/other scalar
        add_email(value, subject)

    if not isinstance(raw_student, dict):
        return {'mentor_emails': [], 'mentor_emails_by_subject': {}}

    # 1) Direct fields
    add_emails(raw_student.get('mentorEmails') or raw_student.get('mentor_emails'))
    add_emails(raw_student.get('mentorEmail') or raw_student.get('mentor_email'))

    # 2) mentors list
    mentors = raw_student.get('mentors')
    if isinstance(mentors, list):
        for m in mentors:
            if not isinstance(m, dict):
                continue
            subject = m.get('subject') or m.get('subjectName') or m.get('name')
            add_emails(m.get('email') or m.get('mentorEmail') or m.get('mentor_email'), subject)

    # 3) subjects/assignments/courses list
    for list_key in ('subjects', 'assignments', 'courses', 'modules'):
        items = raw_student.get(list_key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            subject = item.get('subject') or item.get('name') or item.get('title') or item.get('subjectName')
            add_emails(item.get('mentorEmails') or item.get('mentor_emails'), subject)
            add_emails(item.get('mentorEmail') or item.get('mentor_email'), subject)
            mentor_obj = item.get('mentor')
            if isinstance(mentor_obj, dict):
                add_emails(mentor_obj.get('email') or mentor_obj.get('mentorEmail') or mentor_obj.get('mentor_email'), subject)

    # Normalize per-subject values and flatten
    mentor_emails = _uniq_emails(mentor_emails)
    mentor_emails_by_subject = {
        str(k).strip(): _uniq_emails(v)
        for k, v in mentor_emails_by_subject.items()
        if k and str(k).strip()
    }

    return {
        'mentor_emails': mentor_emails,
        'mentor_emails_by_subject': mentor_emails_by_subject,
    }


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

    extracted = _extract_mentor_emails(match)
    extracted_list = extracted.get('mentor_emails')
    if isinstance(extracted_list, list) and extracted_list:
        mentor_emails = extracted_list
    elif isinstance(mentor_emails, list):
        mentor_emails = [str(x).strip() for x in mentor_emails if x and str(x).strip()]
    elif isinstance(mentor_emails, dict):
        # Some partners return mentorEmails as {subject: email(s)}
        tmp: List[str] = []
        for v in mentor_emails.values():
            if isinstance(v, list):
                tmp.extend([str(x).strip() for x in v if x and str(x).strip()])
            elif v is not None:
                s = str(v).strip()
                if s:
                    tmp.append(s)
        mentor_emails = _uniq_emails(tmp)
    else:
        mentor_emails = []

    profile.update({
        'mentor_emails': mentor_emails,
        'mentor_emails_by_subject': extracted.get('mentor_emails_by_subject') or {},
        'raw': match,
    })

    # Token validity is ~5 minutes; profile changes are infrequent. Cache briefly.
    cache.set(cache_key, profile, 300)
    return profile
