"""
Booking Models - Appointments between students and faculty
"""
import uuid
from django.db import models, transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from core.subjects import normalize_subject


class Booking(models.Model):
    """
    Booking/Appointment model.
    Represents a student booking a faculty's availability slot.
    """
    
    class Status(models.TextChoices):
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'
        COMPLETED = 'completed', 'Completed'
        ABSENT = 'absent', 'Absent'

    # Student cancellation window rule
    STUDENT_CANCELLATION_WINDOW_HOURS = 4
    STUDENT_CANCELLATION_WINDOW_MESSAGE = (
        'Cancellation is not allowed within 4 hours of the scheduled slot.'
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Relationships
    slot = models.OneToOneField(
        'slots.Slot',
        on_delete=models.CASCADE,
        related_name='booking'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bookings',
        limit_choices_to={'role': 'student'}
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
        db_index=True
    )
    
    # Cancellation tracking
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)

    # Absence tracking
    absent_at = models.DateTimeField(null=True, blank=True, db_index=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'bookings'
        verbose_name = 'Booking'
        verbose_name_plural = 'Bookings'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
        constraints = []
    
    def __str__(self):
        return f"{self.student.name} - {self.slot.start_time.strftime('%Y-%m-%d %H:%M')}"

    @classmethod
    def _conflict_queryset(
        cls,
        *,
        student,
        subject: str,
        scope: str,
        slot_date=None,
        now=None,
        for_update: bool = False,
        exclude_pk=None,
    ):
        """Build the queryset used to detect conflicting bookings.

        scope:
          - 'same_day': conflicts are limited to slot__start_time__date == slot_date
          - 'future': conflicts are any slot__start_time__gt now

        Conflicting statuses are consistent across code paths: CONFIRMED and ABSENT.
        """

        if now is None:
            now = timezone.now()

        qs = cls.objects
        if for_update:
            qs = qs.select_for_update()

        qs = qs.filter(
            student=student,
            slot__subject=subject,
            status__in=[cls.Status.CONFIRMED, cls.Status.ABSENT],
        )

        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)

        if scope == 'same_day':
            if slot_date is None:
                raise ValueError('slot_date is required for same_day conflict checks')
            return qs.filter(slot__start_time__date=slot_date)

        if scope == 'future':
            return qs.filter(slot__start_time__gt=now)

        raise ValueError("Invalid scope; expected 'same_day' or 'future'")

    @classmethod
    def validate_no_conflict(
        cls,
        *,
        student,
        subject: str,
        scope: str,
        slot_date=None,
        now=None,
        for_update: bool = False,
        exclude_pk=None,
        message: str = 'You already have a booking for this subject.',
    ) -> None:
        """Raise ValidationError if a conflicting booking exists."""

        if cls._conflict_queryset(
            student=student,
            subject=subject,
            scope=scope,
            slot_date=slot_date,
            now=now,
            for_update=for_update,
            exclude_pk=exclude_pk,
        ).exists():
            raise ValidationError(message)
    
    def clean(self):
        """Validate booking data."""
        if self.pk is None:  # Only on create
            subject = normalize_subject(self.slot.subject)
            teacher_external_id = self.slot.faculty.pbl_user_id

            # Check if slot is available
            if not self.slot.is_available:
                raise ValidationError({'slot': 'This slot is not available'})

            # Check if slot is in the future
            if self.slot.start_time <= timezone.now():
                raise ValidationError({'slot': 'Cannot book a slot in the past'})

            # Enforce 1 slot per subject per day (reset after 7pm)
            slot_date = self.slot.start_time.date()
            now = timezone.now()
            # If after 7pm, allow booking for next day only
            if now.hour >= 19:
                if slot_date == now.date():
                    raise ValidationError('You cannot book slots for today after 7pm. Please book for tomorrow.')
            # Only allow one booking per subject per day (CONFIRMED/ABSENT)
            Booking.validate_no_conflict(
                student=self.student,
                subject=subject,
                scope='same_day',
                slot_date=slot_date,
                exclude_pk=self.pk,
                message='You already have a booking for this subject on this day.',
            )

            latest_absent = (
                Booking.objects.filter(
                    student=self.student,
                    slot__subject=subject,
                    slot__faculty__pbl_user_id=teacher_external_id,
                    status=self.Status.ABSENT,
                )
                .order_by('-absent_at', '-updated_at')
                .first()
            )

            if latest_absent is not None:
                absent_time = latest_absent.absent_at or latest_absent.updated_at
                permission = (
                    RebookingPermission.objects.filter(
                        student=self.student,
                        subject=subject,
                        teacher_external_id=teacher_external_id,
                    )
                    .only('updated_at')
                    .first()
                )

                if permission is None or (absent_time and permission.updated_at < absent_time):
                    raise ValidationError(
                        f'Booking for {subject} is blocked because you were marked absent. '
                        'Your faculty must allow rebooking before you can book another slot.'
                    )
    
    @property
    def can_cancel(self):
        """
        Check if booking can be cancelled.

        Student cancellation is allowed only until 8 hours before the slot time.
        (Faculty cancellation is not restricted by this rule.)
        """
        if self.status != self.Status.CONFIRMED:
            return False

        cancellation_deadline = self.slot.start_time - timedelta(
            hours=self.STUDENT_CANCELLATION_WINDOW_HOURS
        )
        return timezone.now() < cancellation_deadline
    
    @property
    def faculty(self):
        """Get the faculty member for this booking."""
        return self.slot.faculty
    
    @classmethod
    @transaction.atomic
    def create_booking(cls, slot, student):
        """
        Create a new booking with proper transaction handling.
        
        Uses SELECT FOR UPDATE to prevent race conditions.
        """
        from slots.models import Slot
        from core.models import User
        
        # Lock the slot row
        slot = Slot.objects.select_for_update().get(pk=slot.pk)

        # Lock the student row to reduce concurrent absence/permission races
        User.objects.select_for_update().get(pk=student.pk)

        subject = normalize_subject(slot.subject)
        teacher_external_id = slot.faculty.pbl_user_id
        
        # Check if slot is available
        if not slot.is_available:
            raise ValidationError('This slot is no longer available')
        
        # Check if already booked / handle previously cancelled booking (OneToOne)
        existing_booking = None
        try:
            existing_booking = slot.booking
        except cls.DoesNotExist:
            existing_booking = None

        if existing_booking and existing_booking.status == cls.Status.CONFIRMED:
            raise ValidationError('This slot is already booked')

        # Enforce booking rules per (student, subject):
        # - Block only if there's an ACTIVE future booking for this subject (CONFIRMED/ABSENT)
        #   Past bookings should not block re-booking.
        now = timezone.now()
        cls.validate_no_conflict(
            student=student,
            subject=subject,
            scope='future',
            now=now,
            for_update=True,
            message='You already have a booking for this subject.',
        )

        # Absence lock is per-student (not per team). A student's absence should not block teammates.
        latest_absent = (
            cls.objects.select_for_update()
            .filter(
                student=student,
                status=cls.Status.ABSENT,
                slot__subject=subject,
                slot__faculty__pbl_user_id=teacher_external_id,
            )
            .order_by('-absent_at', '-updated_at')
            .first()
        )

        if latest_absent is not None:
            absent_time = latest_absent.absent_at or latest_absent.updated_at
            permission = (
                RebookingPermission.objects.filter(
                    student=student,
                    subject=subject,
                    teacher_external_id=teacher_external_id,
                )
                .only('updated_at')
                .first()
            )

            if permission is None or (absent_time and permission.updated_at < absent_time):
                raise ValidationError(
                    f'Booking for {subject} is blocked because you were marked absent. '
                    'Your faculty must allow rebooking before you can book another slot.'
                )
        
        # Reuse an existing cancelled booking row (allows rebooking the same slot)
        if existing_booking and existing_booking.status == cls.Status.CANCELLED:
            existing_booking.student = student
            existing_booking.status = cls.Status.CONFIRMED
            existing_booking.cancelled_at = None
            existing_booking.cancellation_reason = ''
            existing_booking.save(
                update_fields=[
                    'student',
                    'status',
                    'cancelled_at',
                    'cancellation_reason',
                    'updated_at',
                ]
            )
            booking = existing_booking
        else:
            # Create booking
            booking = cls.objects.create(
                slot=slot,
                student=student,
                status=cls.Status.CONFIRMED
            )
        
        # Mark slot as unavailable
        slot.is_available = False
        slot.save(update_fields=['is_available', 'updated_at'])

        return booking
    
    @transaction.atomic
    def cancel(self, reason='', *, force=False):
        """Cancel the booking.

        By default (force=False), the student cancellation window is enforced.
        Faculty workflows can bypass the time window by calling with force=True.
        """
        if self.status != self.Status.CONFIRMED:
            raise ValidationError('Only confirmed bookings can be cancelled')

        if not force and not self.can_cancel:
            raise ValidationError(self.STUDENT_CANCELLATION_WINDOW_MESSAGE)
        
        self.status = self.Status.CANCELLED
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.save()
        
        # Make slot available again
        self.slot.is_available = True
        self.slot.save(update_fields=['is_available', 'updated_at'])
        
        return self


class RebookingPermission(models.Model):
    """Allows a student to rebook a subject after being marked absent.

    Unique per (student, subject). Created by faculty (identified via teacher_external_id).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='rebooking_permissions',
        limit_choices_to={'role': 'student'},
    )

    subject = models.CharField(max_length=100, db_index=True)

    teacher_external_id = models.CharField(max_length=255, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'rebooking_permissions'
        verbose_name = 'Rebooking Permission'
        verbose_name_plural = 'Rebooking Permissions'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'subject'],
                name='unique_rebooking_permission_per_student_subject'
            )
        ]
        indexes = [
            models.Index(fields=['student', 'subject']),
            models.Index(fields=['teacher_external_id', 'subject']),
        ]

    def __str__(self):
        return f"{self.student.email} can rebook {self.subject}"
