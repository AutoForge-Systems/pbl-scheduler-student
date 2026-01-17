"""
Slot Views
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from django.db.models import Count
from django.db.models import Min
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
    
    @action(detail=False, methods=['get', 'post'], url_path='availability')
    def availability(self, request):
        """
        Get or set teacher's availability status.
        
        GET: Returns current availability status
        POST: Toggle or set availability status
              Body: { "is_available": true/false }
        """
        faculty = request.user
        
        if request.method == 'GET':
            return Response({
                'is_available': faculty.is_available_for_booking
            })
        
        # POST - set availability
        is_available = request.data.get('is_available')
        if is_available is None:
            return Response(
                {'error': 'is_available field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        faculty.is_available_for_booking = bool(is_available)
        faculty.save(update_fields=['is_available_for_booking'])
        
        return Response({
            'message': 'Availability updated successfully',
            'is_available': faculty.is_available_for_booking
        })


class StudentSlotViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for students to view available slots.
    
    IMPORTANT: Students can ONLY see slots from their assigned teachers
    for their assigned subjects. This is enforced by the backend.
    
    Additional: Students CANNOT see slots if the teacher is marked as "Busy".
    
    The assignment comes from PBL system (via SSO).
    No fallback to showing all slots - if no assignment exists, return empty.
    """
    permission_classes = [IsAuthenticated, IsStudent]
    serializer_class = SlotSerializer
    
    def get_queryset(self):
        """
        Return available future slots ONLY from the student's assigned teachers.

        Primary source of truth is local `StudentTeacherAssignment` rows created
        during SSO (one teacher per subject). Fallback to PBL mentorEmails only
        when no local assignments exist.
        """
        from core.assignment_models import StudentTeacherAssignment
        from core.models import User
        from core.pbl_external import get_student_external_profile
        
        student = self.request.user

        mentor_emails: list[str] = []
        teacher_ids = StudentTeacherAssignment.get_assigned_teacher_ids(student)
        if teacher_ids:
            mentor_emails.extend(
                list(
                    User.objects.filter(role='faculty', pbl_user_id__in=teacher_ids)
                    .exclude(email__isnull=True)
                    .exclude(email__exact='')
                    .values_list('email', flat=True)
                )
            )

        # Always union with external PBL mentor list.
        # In production, local assignments may be partial/out-of-date.
        profile = get_student_external_profile(student.email)
        mentor_emails.extend(profile.get('mentor_emails') or [])

        mentor_emails = [str(e).strip() for e in mentor_emails if e and str(e).strip()]
        # De-dup case-insensitively
        seen = set()
        mentor_emails = [e for e in mentor_emails if not (e.lower() in seen or seen.add(e.lower()))]

        if not mentor_emails:
            return Slot.objects.none()
        
        queryset = Slot.objects.filter(
            faculty__email__in=mentor_emails,
            is_available=True,
            start_time__gt=timezone.now(),
            # Only show slots from teachers who are available (not busy)
            faculty__is_available_for_booking=True
        ).select_related('faculty')
        
        # Exclude slots that are already booked
        queryset = queryset.exclude(
            booking__status='confirmed'
        )
        
        return queryset
    
    @action(detail=False, methods=['get'], url_path='teacher-status')
    def teacher_status(self, request):
        """
        Check assigned teacher's availability status.
        
        Returns whether the student's assigned teacher is currently available.
        If teacher is busy, students should see a message instead of slots.
        """
        from core.assignment_models import StudentTeacherAssignment
        from core.models import User
        from core.pbl_external import get_student_external_profile
        
        student = request.user

        mentor_emails: list[str] = []
        teacher_ids = StudentTeacherAssignment.get_assigned_teacher_ids(student)
        if teacher_ids:
            mentor_emails.extend(
                list(
                    User.objects.filter(role='faculty', pbl_user_id__in=teacher_ids)
                    .exclude(email__isnull=True)
                    .exclude(email__exact='')
                    .values_list('email', flat=True)
                )
            )

        # Union with external PBL mentor list.
        profile = get_student_external_profile(student.email)
        mentor_emails.extend(profile.get('mentor_emails') or [])

        mentor_emails = [str(e).strip() for e in mentor_emails if e and str(e).strip()]
        seen = set()
        mentor_emails = [e for e in mentor_emails if not (e.lower() in seen or seen.add(e.lower()))]

        if not mentor_emails:
            return Response({
                'has_assignment': False,
                'message': 'No mentor assigned'
            })
        
        # Check each mentor's status
        teacher_statuses = []
        for mentor_email in mentor_emails:
            try:
                teacher = User.objects.get(
                    email=mentor_email,
                    role='faculty'
                )

                subjects = list(
                    Slot.objects
                    .filter(faculty=teacher)
                    .values_list('subject', flat=True)
                    .distinct()
                )
                subject = subjects[0] if len(subjects) == 1 else None

                teacher_statuses.append({
                    'teacher_name': teacher.name,
                    'subject': subject,
                    'is_available': teacher.is_available_for_booking
                })
            except User.DoesNotExist:
                teacher_statuses.append({
                    'teacher_name': 'Unknown',
                    'subject': None,
                    'is_available': False
                })
        
        # Overall: if any teacher is busy
        any_busy = any(not t['is_available'] for t in teacher_statuses)
        
        return Response({
            'has_assignment': True,
            'teachers': teacher_statuses,
            'any_teacher_busy': any_busy,
            'message': 'Teacher is currently busy. Please check later.' if any_busy else None
        })
    
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

        teacher_ids = StudentTeacherAssignment.get_assigned_teacher_ids(student)
        mentor_emails: list[str] = []
        if teacher_ids:
            mentor_emails.extend(
                list(
                    User.objects.filter(role='faculty', pbl_user_id__in=teacher_ids)
                    .exclude(email__isnull=True)
                    .exclude(email__exact='')
                    .values_list('email', flat=True)
                )
            )

        profile = get_student_external_profile(student.email)
        pbl_emails = profile.get('mentor_emails') or []
        pbl_by_subject = profile.get('mentor_emails_by_subject') or {}
        pbl_source = profile.get('raw_source')
        mentor_emails.extend(pbl_emails)

        mentor_emails = [str(e).strip() for e in mentor_emails if e and str(e).strip()]
        seen = set()
        mentor_emails = [e for e in mentor_emails if not (e.lower() in seen or seen.add(e.lower()))]

        mentor_sources = {
            'assignments': bool(teacher_ids),
            'pbl': bool(pbl_emails),
            'pbl_source': pbl_source,
            'pbl_subject_keys': sorted([str(k) for k in pbl_by_subject.keys()]) if isinstance(pbl_by_subject, dict) else [],
        }

        faculty_statuses = list(
            User.objects.filter(role='faculty', email__in=mentor_emails)
            .values('email', 'name', 'pbl_user_id', 'is_available_for_booking')
        )

        all_slots_qs = Slot.objects.filter(faculty__email__in=mentor_emails)
        all_counts = list(all_slots_qs.values('subject').annotate(n=Count('id')).order_by('subject'))

        available_qs = (
            Slot.objects.filter(
                faculty__email__in=mentor_emails,
                is_available=True,
                start_time__gt=timezone.now(),
                faculty__is_available_for_booking=True,
            )
            .exclude(booking__status='confirmed')
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
            'mentor_emails': mentor_emails,
            'faculty_statuses': faculty_statuses,
            'counts_all_slots_by_subject': all_counts,
            'counts_available_slots_by_subject': available_counts,
            'counts_available_slots_by_faculty': available_by_faculty,
            'next_available_slots_sample': next_slots,
            'server_time_utc': timezone.now(),
            'git_commit': os.environ.get('RENDER_GIT_COMMIT'),
        })
