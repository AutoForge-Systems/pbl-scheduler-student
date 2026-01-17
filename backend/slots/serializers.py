"""
Slot Serializers
"""
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import Slot
from core.serializers import UserMinimalSerializer
from core.subjects import ALLOWED_SUBJECTS, normalize_subject


class SlotSerializer(serializers.ModelSerializer):
    """Serializer for Slot model."""
    
    faculty = UserMinimalSerializer(read_only=True)
    duration_minutes = serializers.ReadOnlyField()
    is_past = serializers.ReadOnlyField()
    has_booking = serializers.SerializerMethodField()
    teacher_external_id = serializers.ReadOnlyField()
    
    class Meta:
        model = Slot
        fields = [
            'id', 'faculty', 'subject', 'start_time', 'end_time', 
            'is_available', 'duration_minutes', 'is_past',
            'has_booking', 'teacher_external_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'faculty', 'created_at', 'updated_at']
    
    def get_has_booking(self, obj):
        """Check if slot has an active booking."""
        return hasattr(obj, 'booking') and obj.booking.status == 'confirmed'


class SlotCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating slots."""

    # Subject is required for a faculty's first slot. After that, it must stay consistent.
    subject = serializers.CharField(required=False, allow_blank=True, max_length=100)
    
    class Meta:
        model = Slot
        fields = ['start_time', 'end_time', 'subject']
    
    def validate_start_time(self, value):
        """Ensure start time is in the future."""
        if value <= timezone.now():
            raise serializers.ValidationError("Start time must be in the future")
        return value
    
    def validate(self, data):
        """Validate slot data."""
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        
        if start_time and end_time:
            if start_time >= end_time:
                raise serializers.ValidationError({
                    'end_time': 'End time must be after start time'
                })
            
            # Check for overlapping slots
            faculty = self.context['request'].user
            exclude_id = self.instance.id if self.instance else None
            
            if Slot.check_overlap(faculty.id, start_time, end_time, exclude_id):
                raise serializers.ValidationError(
                    "This time slot overlaps with an existing slot"
                )
        
        return data

    def _get_existing_faculty_subject(self, faculty):
        """Return the faculty's existing subject if they already have slots.

        Enforces the invariant that a faculty can only have ONE subject.
        """
        existing = list(
            Slot.objects
            .filter(faculty=faculty)
            .values_list('subject', flat=True)
            .distinct()
        )

        existing = [str(s).strip() for s in existing if s and str(s).strip()]
        existing = [s for s in existing if s in ALLOWED_SUBJECTS]
        existing = sorted(set(existing))

        if not existing:
            return None
        if len(existing) != 1:
            raise serializers.ValidationError(
                'Invalid faculty subject mapping: faculty must be assigned to exactly one subject.'
            )
        return existing[0]

    def _resolve_subject(self, faculty, requested_subject: str | None):
        """Resolve faculty subject for slot creation.

        New rule: faculty must have a configured (sticky) subject in the user profile.
        Slot creation always uses that subject.

        Backward compatibility: if faculty_subject is missing but slots already exist,
        we derive the subject from existing slots.
        """
        requested = normalize_subject(requested_subject or '')
        if requested and requested not in ALLOWED_SUBJECTS:
            raise serializers.ValidationError('Invalid subject')

        configured = normalize_subject(getattr(faculty, 'faculty_subject', '') or '')
        if configured:
            if configured not in ALLOWED_SUBJECTS:
                raise serializers.ValidationError('Invalid configured subject')
            if requested and requested != configured:
                raise serializers.ValidationError('Subject is fixed and cannot be changed.')
            return configured

        existing = self._get_existing_faculty_subject(faculty)
        if existing:
            # Backfill for older users.
            try:
                faculty.faculty_subject = existing
                faculty.save(update_fields=['faculty_subject', 'updated_at'])
            except Exception:
                pass
            if requested and requested != existing:
                raise serializers.ValidationError('Subject is fixed and cannot be changed.')
            return existing

        raise serializers.ValidationError(
            'Faculty subject not configured. Please set your subject first.'
        )
    
    def create(self, validated_data):
        """Create slot with faculty from request."""
        faculty = self.context['request'].user
        validated_data['faculty'] = faculty
        validated_data['subject'] = self._resolve_subject(faculty, validated_data.get('subject'))
        return super().create(validated_data)


class BulkSlotCreateSerializer(serializers.Serializer):
    """
    Serializer for bulk slot creation with auto-generation.
    
    Teacher provides:
    - start_time: Overall start time
    - end_time: Overall end time  
    - slot_duration: Duration of each slot in minutes (5, 10, or 15)
    - break_duration: Break between slots in minutes (0, 5, 10, or 15)
    """
    subject = serializers.CharField(required=False, allow_blank=True, max_length=100)
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()
    slot_duration = serializers.ChoiceField(choices=[5, 10, 15])
    break_duration = serializers.ChoiceField(choices=[0, 5, 10, 15])
    
    def validate_start_time(self, value):
        """Ensure start time is in the future."""
        if value <= timezone.now():
            raise serializers.ValidationError("Start time must be in the future")
        return value
    
    def validate(self, data):
        """Validate the time range and slot configuration."""
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        slot_duration = data.get('slot_duration')

        subject = (data.get('subject') or '').strip()
        if subject and subject not in ALLOWED_SUBJECTS:
            raise serializers.ValidationError({'detail': 'Invalid subject'})
        
        if start_time and end_time:
            if start_time >= end_time:
                raise serializers.ValidationError({
                    'end_time': 'End time must be after start time'
                })
            
            # Ensure at least one slot can fit
            total_minutes = (end_time - start_time).total_seconds() / 60
            if total_minutes < slot_duration:
                raise serializers.ValidationError(
                    f"Time range is too short for a {slot_duration}-minute slot"
                )
        
        return data
    
    def generate_slots(self, faculty):
        """
        Generate individual slots based on the configuration.
        Returns list of slot data dictionaries.
        """
        # Subject must be provided for first-time faculty; then stays consistent.
        subject = SlotCreateSerializer(context=self.context)._resolve_subject(
            faculty,
            self.validated_data.get('subject'),
        )
        start_time = self.validated_data['start_time']
        end_time = self.validated_data['end_time']
        slot_duration = self.validated_data['slot_duration']
        break_duration = self.validated_data['break_duration']
        
        slots = []
        current_start = start_time
        
        while True:
            current_end = current_start + timedelta(minutes=slot_duration)
            
            # Check if this slot would exceed the end time
            if current_end > end_time:
                break
            
            # Check for overlap with existing slots
            if not Slot.check_overlap(faculty.id, current_start, current_end):
                slots.append({
                    'faculty': faculty,
                    'subject': subject,
                    'start_time': current_start,
                    'end_time': current_end,
                    'is_available': True
                })
            
            # Move to next slot start (after break)
            current_start = current_end + timedelta(minutes=break_duration)
        
        return slots


class SlotListQuerySerializer(serializers.Serializer):
    """Serializer for slot list query parameters."""
    
    date = serializers.DateField(required=False, help_text="Filter by date (YYYY-MM-DD)")
    faculty_id = serializers.UUIDField(required=False, help_text="Filter by faculty ID")
    available_only = serializers.BooleanField(required=False, default=True)


class SlotWithBookingSerializer(SlotSerializer):
    """Serializer for slot with booking details (for faculty view)."""
    
    booking = serializers.SerializerMethodField()
    
    class Meta(SlotSerializer.Meta):
        fields = SlotSerializer.Meta.fields + ['booking']
    
    def get_booking(self, obj):
        """Get booking details if exists."""
        if hasattr(obj, 'booking'):
            from bookings.serializers import BookingMinimalSerializer
            return BookingMinimalSerializer(obj.booking).data
        return None
