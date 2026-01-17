"""
Booking Serializers
"""
from rest_framework import serializers
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from .models import Booking
from slots.serializers import SlotSerializer
from core.serializers import UserMinimalSerializer
from core.subjects import normalize_subject


class BookingSerializer(serializers.ModelSerializer):
    """Serializer for Booking model."""
    
    slot = SlotSerializer(read_only=True)
    student = UserMinimalSerializer(read_only=True)
    faculty = UserMinimalSerializer(source='slot.faculty', read_only=True)
    can_cancel = serializers.ReadOnlyField()
    
    class Meta:
        model = Booking
        fields = [
            'id', 'slot', 'student', 'faculty', 'status',
            'group_id',
            'absent_at',
            'can_cancel', 'cancelled_at', 'cancellation_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class BookingMinimalSerializer(serializers.ModelSerializer):
    """Minimal booking serializer for nested responses."""
    
    student = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = Booking
        fields = ['id', 'student', 'status', 'created_at']
        read_only_fields = fields


class BookingCreateSerializer(serializers.Serializer):
    """Serializer for creating a booking."""
    
    slot_id = serializers.UUIDField(required=True)
    # group_id is derived server-side from the external teams endpoint.
    # We still accept it from the client for backward compatibility, but it is optional.
    group_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    
    def validate_slot_id(self, value):
        """Validate that the slot exists and is available."""
        from slots.models import Slot
        
        try:
            slot = Slot.objects.get(pk=value)
        except Slot.DoesNotExist:
            raise serializers.ValidationError({'detail': 'Slot not found'})
        
        if not slot.is_available:
            raise serializers.ValidationError({'detail': 'This slot is not available'})
        
        if slot.start_time <= timezone.now():
            raise serializers.ValidationError({'detail': 'Cannot book a slot in the past'})
        
        # Check if already booked
        if hasattr(slot, 'booking') and slot.booking.status == 'confirmed':
            raise serializers.ValidationError({'detail': 'This slot is already booked'})
        
        return value
    
    def validate(self, data):
        """
        Check booking rules:
        1. Group must not have an existing active booking for the same subject
        1b. Student marked absent cannot rebook unless permission exists
        2. Student can only book mentor slots (mentorEmails from external student profile)
        """
        from slots.models import Slot
        from .models import RebookingPermission
        from core.pbl_external import get_student_external_profile
        
        student = self.context['request'].user
        slot = Slot.objects.get(pk=data['slot_id'])
        subject = normalize_subject(slot.subject)
        teacher_external_id = slot.faculty.pbl_user_id

        # Resolve external profile first so we can enforce rules using derived group_id.
        profile = get_student_external_profile(student.email)

        # If configured, prefer local roster (supports lookup by email/roll_number).
        group_source_pref = (getattr(settings, 'GROUP_ID_SOURCE', '') or '').strip().lower()
        if 'local' in group_source_pref:
            try:
                from core.group_roster import get_local_group_info_for_user

                info = get_local_group_info_for_user(student)
                if info:
                    profile['group_id'] = info.group_id
                    profile['is_leader'] = info.is_leader
                    profile['group_source'] = f"local:{info.source_table}"
            except Exception:
                pass

        derived_group_id = (profile.get('group_id') or '').strip()
        if not derived_group_id:
            leader_only = bool(getattr(settings, 'BOOKING_LEADER_ONLY', False))
            if leader_only and 'local' in group_source_pref:
                raise serializers.ValidationError({
                    'detail': (
                        'Your email is not mapped to any group in the roster table. '
                        'Only group leaders can book slots. Please contact support.'
                    )
                })

            raise serializers.ValidationError({
                'detail': (
                    'Unable to determine your team ID from the profile. '
                    'Please contact support.'
                )
            })

        # Optional: only group leaders can book
        if bool(getattr(settings, 'BOOKING_LEADER_ONLY', False)):
            if profile.get('is_leader') is not True:
                raise serializers.ValidationError({
                    'detail': 'Only the group leader can book a slot for the team.'
                })

        requested_group_id = (data.get('group_id') or '').strip()
        if requested_group_id and requested_group_id != derived_group_id:
            raise serializers.ValidationError({
                'detail': 'Invalid group_id for this student.'
            })

        existing = Booking.objects.filter(
            group_id=derived_group_id,
            slot__subject=subject,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.ABSENT],
        )

        if existing.filter(status=Booking.Status.CONFIRMED).exists():
            raise serializers.ValidationError({'detail': 'Your team already has a booking for this subject.'})

        latest_absent = (
            Booking.objects.filter(
                student=student,
                status=Booking.Status.ABSENT,
                slot__subject=subject,
                slot__faculty__pbl_user_id=teacher_external_id,
            )
            .order_by('-absent_at', '-updated_at')
            .first()
        )

        if latest_absent is not None:
            absent_time = getattr(latest_absent, 'absent_at', None) or latest_absent.updated_at
            permission = RebookingPermission.objects.filter(
                student=student,
                subject=subject,
                teacher_external_id=teacher_external_id,
            ).only('updated_at').first()

            if permission is None or (absent_time and permission.updated_at < absent_time):
                raise serializers.ValidationError({
                    'detail': (
                        f'Booking for {subject} is blocked because you were marked absent. '
                        'Your faculty must allow rebooking before you can book another slot.'
                    )
                })

        # Always use the derived teamId for enforcement/persistence
        data['group_id'] = derived_group_id

        raw_mentor_emails = profile.get('mentor_emails') or []
        mentor_emails = {
            str(e).strip().lower()
            for e in raw_mentor_emails
            if e is not None and str(e).strip()
        }
        if not mentor_emails:
            raise serializers.ValidationError({
                'detail': (
                    "Unable to determine your mentors from the external student profile. "
                    "Please contact support."
                )
            })

        faculty_email = (getattr(slot.faculty, 'email', '') or '').strip().lower()
        if not faculty_email or faculty_email not in mentor_emails:
            raise serializers.ValidationError({
                'detail': 'You are not authorized to book this slot.'
            })
        
        return data
    
    def create(self, validated_data):
        """Create the booking using the model's transaction-safe method."""
        from slots.models import Slot
        
        slot = Slot.objects.get(pk=validated_data['slot_id'])
        student = self.context['request'].user

        return Booking.create_booking(slot, student, group_id=validated_data['group_id'])


class BookingCancelSerializer(serializers.Serializer):
    """Serializer for cancelling a booking."""
    
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)
    
    def validate(self, data):
        """Check if booking can be cancelled."""
        booking = self.context['booking']
        
        if booking.status != Booking.Status.CONFIRMED:
            raise serializers.ValidationError({'detail': 'Only confirmed bookings can be cancelled'})
        
        if not booking.can_cancel:
            raise serializers.ValidationError({'detail': Booking.STUDENT_CANCELLATION_WINDOW_MESSAGE})
        
        return data
