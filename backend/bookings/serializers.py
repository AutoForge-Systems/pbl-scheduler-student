"""
Booking Serializers
"""
from rest_framework import serializers
from django.utils import timezone
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
    student_id = serializers.SerializerMethodField(read_only=True)
    can_cancel = serializers.ReadOnlyField()

    def get_student_id(self, obj):
        student = getattr(obj, 'student', None)
        return getattr(student, 'pbl_user_id', None)
    
    class Meta:
        model = Booking
        fields = [
                'id', 'slot', 'student', 'student_id', 'faculty', 'status',
            'absent_at',
            'can_cancel', 'cancelled_at', 'cancellation_reason',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields


class BookingMinimalSerializer(serializers.ModelSerializer):
    """Minimal booking serializer for nested responses."""
    
    student = UserMinimalSerializer(read_only=True)
    student_id = serializers.SerializerMethodField(read_only=True)

    def get_student_id(self, obj):
        student = getattr(obj, 'student', None)
        return getattr(student, 'pbl_user_id', None)
    
    class Meta:
        model = Booking
        fields = ['id', 'student', 'student_id', 'status', 'created_at']
        read_only_fields = fields


class BookingCreateSerializer(serializers.Serializer):
    """Serializer for creating a booking."""
    
    slot_id = serializers.UUIDField(required=True)
    
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
        1. Student must not have an existing active booking for the same subject on the same day (handled in model).
        2. Student can only book mentor slots (mentorEmails from external student profile)
        """
        from slots.models import Slot
        from core.pbl_external import get_student_external_profile

        student = self.context['request'].user
        slot = Slot.objects.get(pk=data['slot_id'])
        subject = normalize_subject(slot.subject)

        # Mentor check (unchanged)
        profile = get_student_external_profile(student.email)
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

        return Booking.create_booking(slot, student)


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
