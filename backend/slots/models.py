"""
Slot Models - Availability slots for faculty
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone


class Slot(models.Model):
    """
    Availability slot created by faculty.
    Represents a time window when faculty is available for appointments.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    faculty = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='slots',
        limit_choices_to={'role': 'faculty'}
    )
    
    # Subject for this slot - required, used for student visibility filtering
    # Default is for migration purposes only - new slots must specify subject
    subject = models.CharField(max_length=100, db_index=True, default='General')
    
    # Time fields - stored in UTC
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    
    # Availability status
    is_available = models.BooleanField(default=True, db_index=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'slots'
        verbose_name = 'Slot'
        verbose_name_plural = 'Slots'
        ordering = ['start_time']
        indexes = [
            models.Index(fields=['faculty', 'start_time']),
            models.Index(fields=['is_available', 'start_time']),
            models.Index(fields=['faculty', 'subject', 'is_available']),
        ]
    
    def __str__(self):
        return f"{self.faculty.name} ({self.subject}): {self.start_time.strftime('%Y-%m-%d %H:%M')} - {self.end_time.strftime('%H:%M')}"
    
    @property
    def teacher_external_id(self):
        """Get the teacher's external PBL ID for assignment matching."""
        return self.faculty.pbl_user_id
    
    def clean(self):
        """Validate slot data."""
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                raise ValidationError({
                    'end_time': 'End time must be after start time'
                })
            
            if self.start_time < timezone.now():
                raise ValidationError({
                    'start_time': 'Start time cannot be in the past'
                })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def duration_minutes(self):
        """Get slot duration in minutes."""
        delta = self.end_time - self.start_time
        return int(delta.total_seconds() / 60)
    
    @property
    def is_past(self):
        """Check if slot is in the past."""
        return self.start_time < timezone.now()
    
    @property
    def is_booked(self):
        """Check if slot has an active booking."""
        return hasattr(self, 'booking') and self.booking.status == 'confirmed'
    
    @classmethod
    def get_available_slots(cls):
        """Get all available future slots."""
        return cls.objects.filter(
            is_available=True,
            start_time__gt=timezone.now()
        ).select_related('faculty')
    
    @classmethod
    def check_overlap(cls, faculty_id, start_time, end_time, exclude_id=None):
        """
        Check if there are overlapping slots for a faculty member.
        
        Returns True if overlap exists, False otherwise.
        """
        queryset = cls.objects.filter(
            faculty_id=faculty_id,
            start_time__lt=end_time,
            end_time__gt=start_time
        )
        
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        
        return queryset.exists()
