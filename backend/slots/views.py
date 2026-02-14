"""
Slot Views
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import Count
from django.db.models import Min
from django.db.models import Q
import os
from datetime import datetime, timedelta

from .models import Slot
from .serializers import (
    SlotSerializer, 
    SlotCreateSerializer, 
    SlotWithBookingSerializer,
    SlotListQuerySerializer,
    BulkSlotCreateSerializer
)
from core.permissions import IsFaculty, IsStudent
from core.subjects import ALLOWED_SUBJECTS, normalize_subject, is_allowed_subject


class SlotAvailabilitySummaryView(APIView):
    """Public-ish endpoint for the main PBL site to check slot availability per subject.

    Auth is via a shared secret header (not a user JWT) because the PBL site is a separate app.

    GET /api/v1/slots/availability-summary/
    Headers:
      - X-PBL-Scheduler-Secret: <shared-secret>

    Response:
      {
        "generated_at": "...",
        "subjects": [{"subject": "Web Development", "has_available_slots": true}, ...]
      }
    """

    permission_classes = []

    _HEADER_NAME = 'HTTP_X_PBL_SCHEDULER_SECRET'

    def get(self, request):
        configured = (getattr(settings, 'PBL_SCHEDULER_SHARED_SECRET', '') or '').strip()
        provided = (request.META.get(self._HEADER_NAME) or '').strip()

        # If a secret is configured, enforce it always.
        if configured:
            if not provided or provided != configured:
                return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        else:
            # If no secret configured, allow only in DEBUG for local development.
            if not getattr(settings, 'DEBUG', False):
                return Response(
                    {'detail': 'Service not configured (missing PBL_SCHEDULER_SHARED_SECRET).'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        now = timezone.now()

        available_by_subject = {
            row['subject']: True
            for row in (
                Slot.objects.filter(
                    is_available=True,
                    start_time__gt=now,
                )
                .exclude(booking__status='confirmed')
                .values('subject')
                .distinct()
            )
        }

        subjects_sorted = sorted(ALLOWED_SUBJECTS, key=lambda s: str(s).lower())
        payload_subjects = [
            {
                'subject': subject,
                'has_available_slots': bool(available_by_subject.get(subject)),
            }
            for subject in subjects_sorted
        ]

        return Response(
            {
                'generated_at': timezone.now().isoformat(),
                'subjects': payload_subjects,
            }
        )


class StudentSubjectAvailabilityView(APIView):
    """Server-to-server endpoint for PBL to check availability for a specific student.

    GET /api/v1/slots/student-availability/?email=<student-email>&subjects=Web%20Development,Compiler%20Design
    Header: X-PBL-Scheduler-Secret: <shared-secret>

    The returned availability is computed for the student's mapped mentors per subject.
    """

    permission_classes = []

    _HEADER_NAME = 'HTTP_X_PBL_SCHEDULER_SECRET'

    def get(self, request):
        configured = (getattr(settings, 'PBL_SCHEDULER_SHARED_SECRET', '') or '').strip()
        provided = (request.META.get(self._HEADER_NAME) or '').strip()

        if configured:
            if not provided or provided != configured:
                return Response({'detail': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)
        else:
            if not getattr(settings, 'DEBUG', False):
                return Response(
                    {'detail': 'Service not configured (missing PBL_SCHEDULER_SHARED_SECRET).'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        email = (request.query_params.get('email') or request.query_params.get('student_email') or '').strip()
        if not email:
            return Response({'detail': 'Missing required query param: email'}, status=status.HTTP_400_BAD_REQUEST)

        subjects_param = (request.query_params.get('subjects') or '').strip()
        if subjects_param:
            requested_subjects = [normalize_subject(s) for s in subjects_param.split(',') if normalize_subject(s)]
        else:
            requested_subjects = ['Web Development', 'Compiler Design']

        requested_subjects = [s for s in requested_subjects if is_allowed_subject(s)]
        if not requested_subjects:
            return Response(
                {
                    'detail': 'No valid subjects requested.',
                    'allowed_subjects': sorted(ALLOWED_SUBJECTS, key=lambda x: str(x).lower()),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from core.models import User
        from core.assignment_models import StudentTeacherAssignment
        from core.pbl_external import get_student_external_profile

        profile = get_student_external_profile(email) or {}
        by_subject = profile.get('mentor_emails_by_subject') or {}

        mentor_emails_by_subject: dict[str, list[str]] = {}
        if isinstance(by_subject, dict) and by_subject:
            for subject_key, mentor_emails in by_subject.items():
                subject = normalize_subject(subject_key)
                if not subject or not is_allowed_subject(subject):
                    continue
                if not isinstance(mentor_emails, list):
                    continue
                cleaned = [str(e).strip() for e in mentor_emails if e and str(e).strip()]
                if cleaned:
                    mentor_emails_by_subject[subject] = cleaned

        # Fallback: local assignments
        if not mentor_emails_by_subject:
            student = User.objects.filter(email__iexact=email, role=User.Role.STUDENT).first()
            if student is not None:
                rows = list(
                    StudentTeacherAssignment.objects.filter(student=student)
                    .values_list('subject', 'teacher_external_id')
                )
                teacher_ids = [tid for (_, tid) in rows if tid]
                teachers = {
                    u.pbl_user_id: (u.email or '').strip()
                    for u in User.objects.filter(role=User.Role.FACULTY, pbl_user_id__in=teacher_ids)
                    if u.pbl_user_id
                }
                for subj, teacher_id in rows:
                    subj_n = normalize_subject(subj)
                    if not subj_n or not is_allowed_subject(subj_n):
                        continue
                    email_v = (teachers.get(teacher_id) or '').strip()
                    if not email_v:
                        continue
                    mentor_emails_by_subject.setdefault(subj_n, []).append(email_v)

        now = timezone.now()
        payload_subjects = []

        for subject in requested_subjects:
            mentors = mentor_emails_by_subject.get(subject) or []
            # de-dup (case-insensitive)
            seen = set()
            mentors = [m for m in mentors if not (m.lower() in seen or seen.add(m.lower()))]

            if not mentors:
                qs = (
                    Slot.objects.filter(
                        subject=subject,
                        is_available=True,
                        start_time__gt=now,
                    )
                    .exclude(booking__status='confirmed')
                    .order_by('start_time')
                )
                next_slot = qs.first()
                payload_subjects.append(
                    {
                        'subject': subject,
                        'mentor_emails': [],
                        'has_available_slots': qs.exists(),
                        'available_count': qs.count(),
                        'next_slot_start_time': next_slot.start_time.isoformat() if next_slot else None,
                    }
                )
                continue

            qs = (
                Slot.objects.filter(
                    subject=subject,
                    faculty__email__in=mentors,
                    is_available=True,
                    start_time__gt=now,
                )
                .exclude(booking__status='confirmed')
                .order_by('start_time')
            )

            next_slot = qs.first()
            payload_subjects.append(
                {
                    'subject': subject,
                    'mentor_emails': mentors,
                    'has_available_slots': qs.exists(),
                    'available_count': qs.count(),
                    'next_slot_start_time': next_slot.start_time.isoformat() if next_slot else None,
                }
            )

        return Response(
            {
                'generated_at': timezone.now().isoformat(),
                'student_email': email,
                'subjects': payload_subjects,
            }
        )


class FacultySlotViewSet(viewsets.ModelViewSet):
    """
    ViewSet for faculty to manage their slots.
    
    Faculty can:
    - Create new availability slots
    - View their own slots
    - Update their slots (if not booked)
    - Delete their slots (if not booked)
    """
    permission_classes = [IsAuthenticated, IsFaculty]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return SlotCreateSerializer
        return SlotWithBookingSerializer
    
    def get_queryset(self):
        """Return only the faculty's own slots."""
        return Slot.objects.filter(
            faculty=self.request.user
        ).select_related('faculty').prefetch_related('booking')
    
    def list(self, request):
        """List faculty's slots with optional filters."""
        queryset = self.get_queryset()
        
        # Filter by date if provided
        date_str = request.query_params.get('date')
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_of_day = timezone.make_aware(
                    datetime.combine(date, datetime.min.time())
                )
                end_of_day = start_of_day + timedelta(days=1)
                queryset = queryset.filter(
                    start_time__gte=start_of_day,
                    start_time__lt=end_of_day
                )
            except ValueError:
                pass
        
        # Filter future only
        if request.query_params.get('future_only', 'true').lower() == 'true':
            queryset = queryset.filter(start_time__gt=timezone.now())
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    def destroy(self, request, *args, **kwargs):
        """Delete slot only if safe.

        Safety rule:
        - Never delete if slot has a confirmed/completed/absent booking (preserve history)
        - Allow deletion for open slots and slots with cancelled bookings
        """
        slot = self.get_object()

        if hasattr(slot, 'booking') and slot.booking is not None:
            booking_status = getattr(slot.booking, 'status', None)
            if booking_status in ['confirmed', 'completed', 'absent']:
                return Response(
                    {'error': 'Cannot delete a slot that has booking history'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        
        slot.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """
        Create multiple slots from a time range with auto-generation.
        
        Teacher provides:
        - subject: Subject for all slots
        - start_time: Overall start time (ISO format)
        - end_time: Overall end time (ISO format)
        - slot_duration: Duration of each slot in minutes (5, 10, or 15)
        - break_duration: Break between slots in minutes (0, 5, 10, or 15)
        
        Backend auto-generates individual slots.
        """
        serializer = BulkSlotCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        faculty = request.user
        slots_data = serializer.generate_slots(faculty)
        
        if not slots_data:
            return Response(
                {'error': 'No valid slots could be generated. Check for overlaps or invalid time range.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create all slots in a transaction
        created_slots = []
        with transaction.atomic():
            for slot_data in slots_data:
                slot = Slot.objects.create(**slot_data)
                created_slots.append(slot)
        
        return Response({
            'message': f'Successfully created {len(created_slots)} slots',
            'slots_count': len(created_slots),
            'slots': SlotWithBookingSerializer(created_slots, many=True).data
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get', 'post'], url_path='subject')
    def subject(self, request):
        """Return the faculty's configured subject.

        Source of truth is the faculty user's stored subject (`users.faculty_subject`).
        If missing, we fall back to deriving from existing slots (and will backfill
        the user field when the mapping is unambiguous).

        POST sets the subject only if it is not already set (sticky).

        Response:
          {"subject": "Web Development" | "Compiler Design" | null,
           "status": "set" | "not_set",
           "allowed_subjects": [..]}
        """
        faculty = request.user

        if request.method == 'POST':
            if normalize_subject(getattr(faculty, 'faculty_subject', '') or ''):
                return Response(
                    {
                        'detail': 'Subject is already configured and cannot be changed.',
                        'subject': normalize_subject(faculty.faculty_subject),
                        'status': 'set',
                        'allowed_subjects': sorted(ALLOWED_SUBJECTS),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            requested = normalize_subject((request.data or {}).get('subject') or '')
            if not requested:
                return Response(
                    {'detail': 'Subject is required', 'allowed_subjects': sorted(ALLOWED_SUBJECTS)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not is_allowed_subject(requested):
                return Response(
                    {'detail': 'Invalid subject', 'allowed_subjects': sorted(ALLOWED_SUBJECTS)},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # If slots exist already, enforce consistency.
            existing_subjects = list(
                Slot.objects.filter(faculty=faculty)
                .values_list('subject', flat=True)
                .distinct()
            )
            existing_subjects = [normalize_subject(s) for s in existing_subjects if normalize_subject(s)]
            existing_subjects = [s for s in existing_subjects if s in ALLOWED_SUBJECTS]
            existing_subjects = sorted(set(existing_subjects))
            if len(existing_subjects) == 1 and existing_subjects[0] != requested:
                return Response(
                    {
                        'detail': 'Subject cannot be changed once slots exist.',
                        'subject': existing_subjects[0],
                        'status': 'set',
                        'allowed_subjects': sorted(ALLOWED_SUBJECTS),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if len(existing_subjects) > 1:
                return Response(
                    {
                        'detail': (
                            'Invalid faculty subject mapping: faculty must be assigned to exactly one subject.'
                        ),
                        'subjects': existing_subjects,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            faculty.faculty_subject = requested
            faculty.save(update_fields=['faculty_subject', 'updated_at'])
            return Response(
                {
                    'subject': requested,
                    'status': 'set',
                    'allowed_subjects': sorted(ALLOWED_SUBJECTS),
                },
                status=status.HTTP_200_OK,
            )

        # GET
        configured = normalize_subject(getattr(faculty, 'faculty_subject', '') or '')
        if configured:
            if configured not in ALLOWED_SUBJECTS:
                return Response(
                    {
                        'detail': 'Invalid configured subject',
                        'subject': configured,
                        'allowed_subjects': sorted(ALLOWED_SUBJECTS),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {
                    'subject': configured,
                    'status': 'set',
                    'allowed_subjects': sorted(ALLOWED_SUBJECTS),
                },
                status=status.HTTP_200_OK,
            )

        subjects = list(
            Slot.objects.filter(faculty=faculty)
            .values_list('subject', flat=True)
            .distinct()
        )

        subjects = [normalize_subject(s) for s in subjects if normalize_subject(s)]
        subjects = [s for s in subjects if s in ALLOWED_SUBJECTS]
        subjects = sorted(set(subjects))

        if not subjects:
            return Response(
                {
                    'subject': None,
                    'status': 'not_set',
                    'allowed_subjects': sorted(ALLOWED_SUBJECTS),
                },
                status=status.HTTP_200_OK,
            )

        if len(subjects) != 1:
            return Response(
                {
                    'detail': (
                        'Invalid faculty subject mapping: faculty must be assigned to exactly one subject.'
                    ),
                    'subjects': subjects,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Backfill user field for existing faculty.
        faculty.faculty_subject = subjects[0]
        faculty.save(update_fields=['faculty_subject', 'updated_at'])

        return Response(
            {
                'subject': subjects[0],
                'status': 'set',
                'allowed_subjects': sorted(ALLOWED_SUBJECTS),
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['delete'], url_path="delete-todays-slots")
    def delete_todays_slots(self, request):
        """Delete all of the logged-in faculty's slots for today.

        - Deletes slots for TODAY's date (in server timezone)
        - Safety: will NOT delete slots with a confirmed booking
        - To avoid losing attendance history, also skips slots with completed/absent bookings
        - Must be atomic
        """
        from bookings.models import Booking

        faculty = request.user
        today = timezone.localdate()

        start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end_of_day = start_of_day + timedelta(days=1)

        qs = Slot.objects.filter(
            faculty=faculty,
            start_time__gte=start_of_day,
            start_time__lt=end_of_day,
        )

        confirmed_count = qs.filter(booking__status=Booking.Status.CONFIRMED).count()
        if confirmed_count:
            return Response(
                {
                    'detail': (
                        "Cannot delete today's slots because you have "
                        f"{confirmed_count} confirmed booking(s). Cancel those bookings first."
                    ),
                    'confirmed_count': confirmed_count,
                    'date': str(today),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only delete open slots and slots with cancelled bookings; keep completed/absent history.
        deletable_qs = qs.exclude(
            booking__status__in=[
                Booking.Status.CONFIRMED,
                Booking.Status.COMPLETED,
                Booking.Status.ABSENT,
            ]
        )

        total_count = qs.count()
        deletable_count = deletable_qs.count()

        with transaction.atomic():
            deleted_count, _ = deletable_qs.delete()

        return Response({
            'message': f"Deleted today's slots successfully",
            'deleted_count': deleted_count,
            'skipped_count': total_count - deletable_count,
            'date': str(today),
        })


class StudentSlotViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for students to view available slots.
    
    IMPORTANT: Students can ONLY see slots from their assigned teachers
    for their assigned subjects. This is enforced by the backend.
    
    The assignment comes from PBL system (via SSO).
    No fallback to showing all slots - if no assignment exists, return empty.
    """
    permission_classes = [IsAuthenticated, IsStudent]
    serializer_class = SlotSerializer
    
    def get_queryset(self):
        """
        Return available future slots ONLY for the student's assigned subjects and mentors.

        Source of truth:
        1) PBL-provided `mentor_emails_by_subject` (preferred)
        2) Local `StudentTeacherAssignment` rows (fallback)

        If no subject mapping exists, return empty.
        """
        from core.assignment_models import StudentTeacherAssignment
        from core.models import User
        from core.pbl_external import get_student_external_profile
        
        student = self.request.user

        profile = get_student_external_profile(student.email) or {}
        pbl_by_subject = profile.get('mentor_emails_by_subject') or {}

        mentor_emails_by_subject: dict[str, list[str]] = {}
        if isinstance(pbl_by_subject, dict) and pbl_by_subject:
            for subject_key, mentor_emails in pbl_by_subject.items():
                subject = normalize_subject(subject_key)
                if not subject or not is_allowed_subject(subject):
                    continue
                if not isinstance(mentor_emails, list):
                    continue
                cleaned = [str(e).strip() for e in mentor_emails if e and str(e).strip()]
                if cleaned:
                    # de-dup case-insensitively
                    seen = set()
                    cleaned = [e for e in cleaned if not (e.lower() in seen or seen.add(e.lower()))]
                    mentor_emails_by_subject[subject] = cleaned

        # Fallback: local assignments (subject -> faculty email)
        if not mentor_emails_by_subject:
            rows = list(
                StudentTeacherAssignment.objects.filter(student=student)
                .values_list('subject', 'teacher_external_id')
            )
            teacher_ids = [tid for (_, tid) in rows if tid]

            if teacher_ids:
                teachers = {
                    u.pbl_user_id: (u.email or '').strip()
                    for u in User.objects.filter(role=User.Role.FACULTY, pbl_user_id__in=teacher_ids)
                    if u.pbl_user_id
                }
                for subj, teacher_id in rows:
                    subject = normalize_subject(subj)
                    if not subject or not is_allowed_subject(subject):
                        continue
                    email_v = (teachers.get(teacher_id) or '').strip()
                    if not email_v:
                        continue
                    mentor_emails_by_subject.setdefault(subject, []).append(email_v)

            if mentor_emails_by_subject:
                for subject, emails in list(mentor_emails_by_subject.items()):
                    seen = set()
                    mentor_emails_by_subject[subject] = [
                        e for e in emails if e and not (e.lower() in seen or seen.add(e.lower()))
                    ]

        if not mentor_emails_by_subject:
            return Slot.objects.none()

        visibility_q = Q()
        for subject, emails in mentor_emails_by_subject.items():
            if emails:
                visibility_q |= Q(subject=subject, faculty__email__in=emails)

        if not visibility_q:
            return Slot.objects.none()

        queryset = Slot.objects.filter(
            visibility_q,
            is_available=True,
            start_time__gt=timezone.now(),
        ).select_related('faculty')
        
        # Exclude slots that are already booked
        queryset = queryset.exclude(
            booking__status='confirmed'
        )
        
        return queryset
    
    def list(self, request):
        """List available slots with optional filters."""
        queryset = self.get_queryset()
        
        # Filter by date
        date_str = request.query_params.get('date')
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                start_of_day = timezone.make_aware(
                    datetime.combine(date, datetime.min.time())
                )
                end_of_day = start_of_day + timedelta(days=1)
                queryset = queryset.filter(
                    start_time__gte=start_of_day,
                    start_time__lt=end_of_day
                )
            except ValueError:
                pass
        
        # Note: faculty_id filter removed - students can only see assigned teachers
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='debug')
    def debug(self, request):
        """Debug helper for diagnosing missing subjects/teachers.

        Returns which mentor emails are being used and how many available slots
        exist per subject after applying the same filters as the list endpoint.

        Safe for students: returns only aggregate counts and the student's mentor emails.
        """
        from core.assignment_models import StudentTeacherAssignment
        from core.models import User
        from core.pbl_external import get_student_external_profile

        student = request.user

        assignment_rows = list(
            StudentTeacherAssignment.objects.filter(student=student)
            .values('subject', 'teacher_external_id')
            .order_by('subject')
        )

        profile = get_student_external_profile(student.email)
        pbl_by_subject = profile.get('mentor_emails_by_subject') or {}
        pbl_source = profile.get('raw_source')

        # Build the same subject->emails mapping used by get_queryset
        mentor_emails_by_subject: dict[str, list[str]] = {}
        if isinstance(pbl_by_subject, dict) and pbl_by_subject:
            for subject_key, mentor_emails in pbl_by_subject.items():
                subject = normalize_subject(subject_key)
                if not subject or not is_allowed_subject(subject):
                    continue
                if not isinstance(mentor_emails, list):
                    continue
                cleaned = [str(e).strip() for e in mentor_emails if e and str(e).strip()]
                if cleaned:
                    seen = set()
                    cleaned = [e for e in cleaned if not (e.lower() in seen or seen.add(e.lower()))]
                    mentor_emails_by_subject[subject] = cleaned

        teacher_ids = []
        if not mentor_emails_by_subject:
            rows = list(
                StudentTeacherAssignment.objects.filter(student=student)
                .values_list('subject', 'teacher_external_id')
            )
            teacher_ids = [tid for (_, tid) in rows if tid]
            if teacher_ids:
                teachers = {
                    u.pbl_user_id: (u.email or '').strip()
                    for u in User.objects.filter(role=User.Role.FACULTY, pbl_user_id__in=teacher_ids)
                    if u.pbl_user_id
                }
                for subj, teacher_id in rows:
                    subject = normalize_subject(subj)
                    if not subject or not is_allowed_subject(subject):
                        continue
                    email_v = (teachers.get(teacher_id) or '').strip()
                    if not email_v:
                        continue
                    mentor_emails_by_subject.setdefault(subject, []).append(email_v)

        for subject, emails in list(mentor_emails_by_subject.items()):
            seen = set()
            mentor_emails_by_subject[subject] = [
                e for e in emails if e and not (e.lower() in seen or seen.add(e.lower()))
            ]

        mentor_emails = sorted({e for emails in mentor_emails_by_subject.values() for e in emails})

        mentor_sources = {
            'assignments': bool(teacher_ids),
            'pbl': bool(mentor_emails_by_subject) and isinstance(pbl_by_subject, dict) and bool(pbl_by_subject),
            'pbl_source': pbl_source,
            'pbl_subject_keys': sorted([str(k) for k in pbl_by_subject.keys()]) if isinstance(pbl_by_subject, dict) else [],
        }

        faculty_statuses = list(
            User.objects.filter(role='faculty', email__in=mentor_emails)
            .values('email', 'name', 'pbl_user_id')
        )

        existing_emails = {(row.get('email') or '').strip().lower() for row in faculty_statuses}
        missing_mentor_emails = [e for e in mentor_emails if e.lower() not in existing_emails]

        visibility_q = Q()
        for subject, emails in mentor_emails_by_subject.items():
            if emails:
                visibility_q |= Q(subject=subject, faculty__email__in=emails)

        all_slots_qs = Slot.objects.filter(visibility_q) if visibility_q else Slot.objects.none()
        all_counts = list(all_slots_qs.values('subject').annotate(n=Count('id')).order_by('subject'))

        all_by_faculty = list(
            all_slots_qs.values('faculty__email')
            .annotate(n=Count('id'), next_start=Min('start_time'))
            .order_by('faculty__email')
        )

        future_slots_qs = (
            Slot.objects.filter(visibility_q, start_time__gt=timezone.now())
            if visibility_q
            else Slot.objects.none()
        )
        future_by_faculty = list(
            future_slots_qs.values('faculty__email')
            .annotate(n=Count('id'), next_start=Min('start_time'))
            .order_by('faculty__email')
        )

        available_qs = (
            Slot.objects.filter(
                visibility_q,
                is_available=True,
                start_time__gt=timezone.now(),
            ).exclude(booking__status='confirmed')
            if visibility_q
            else Slot.objects.none()
        )
        available_counts = list(available_qs.values('subject').annotate(n=Count('id')).order_by('subject'))

        available_by_faculty = list(
            available_qs.values('faculty__email')
            .annotate(n=Count('id'), next_start=Min('start_time'))
            .order_by('faculty__email')
        )

        # Small sample: next 3 available slots (across mentors)
        next_slots = list(
            available_qs.order_by('start_time')
            .values('id', 'subject', 'start_time', 'faculty__email')[:3]
        )

        return Response({
            'student_email': student.email,
            'mentor_sources': mentor_sources,
            'assignment_rows': assignment_rows,
            'teacher_ids': teacher_ids,
            'mentor_emails_by_subject': mentor_emails_by_subject,
            'mentor_emails': mentor_emails,
            'missing_mentor_emails': missing_mentor_emails,
            'faculty_statuses': faculty_statuses,
            'counts_all_slots_by_subject': all_counts,
            'counts_all_slots_by_faculty': all_by_faculty,
            'counts_future_slots_by_faculty': future_by_faculty,
            'counts_available_slots_by_subject': available_counts,
            'counts_available_slots_by_faculty': available_by_faculty,
            'next_available_slots_sample': next_slots,
            'server_time_utc': timezone.now(),
            'git_commit': os.environ.get('RENDER_GIT_COMMIT'),
        })
