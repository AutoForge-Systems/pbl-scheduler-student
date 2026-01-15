"""
Slot Serializers
"""
from rest_framework import serializers
from django.utils import timezone
from datetime import timedelta
from .models import Slot
from core.serializers import UserMinimalSerializer
from core.subjects import ALLOWED_SUBJECTS


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
    
    class Meta:
        model = Slot
        fields = ['start_time', 'end_time']
    
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

    def _get_faculty_subject(self, faculty):
        """Resolve faculty's fixed subject from authoritative assignment data.

        Temporary rule enforcement (no schema change):
        - faculty must be associated with exactly one subject
        - subject must be one of ALLOWED_SUBJECTS
        """
        from core.assignment_models import StudentTeacherAssignment

        if not faculty.pbl_user_id:
            raise serializers.ValidationError(
                'Faculty subject not configured (missing PBL ID).'
            )

        assignment_subjects = list(
            StudentTeacherAssignment.objects
            .filter(teacher_external_id=faculty.pbl_user_id)
            .values_list('subject', flat=True)
            .distinct()
        )

        assignment_subjects = [s.strip() for s in assignment_subjects if s and s.strip()]
        assignment_subjects = [s for s in assignment_subjects if s in ALLOWED_SUBJECTS]

        slot_subjects = list(
            Slot.objects
            .filter(faculty=faculty)
            .values_list('subject', flat=True)
            .distinct()
        )
        slot_subjects = [s.strip() for s in slot_subjects if s and s.strip()]
        slot_subjects = [s for s in slot_subjects if s in ALLOWED_SUBJECTS]

        combined = sorted(set(assignment_subjects + slot_subjects))

        if not combined:
            raise serializers.ValidationError(
                'Faculty subject not configured. Add a valid subject mapping or create an initial slot with a valid subject.'
            )

        unique_subjects = combined
        if len(unique_subjects) != 1:
            raise serializers.ValidationError(
                'Invalid faculty subject mapping: faculty must be assigned to exactly one subject.'
            )

        return unique_subjects[0]
    
    def create(self, validated_data):
        """Create slot with faculty from request."""
        faculty = self.context['request'].user
        validated_data['faculty'] = faculty
        validated_data['subject'] = self._get_faculty_subject(faculty)
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
        # Subject is derived from faculty mapping (single subject per faculty)
        subject = SlotCreateSerializer(context=self.context)._get_faculty_subject(faculty)
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
