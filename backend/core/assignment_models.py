"""
Assignment Models - Student-Teacher-Subject Mapping

This module defines the mapping between students, teachers, and subjects.
The source of truth for these assignments is the PBL system.
The scheduler only stores and enforces visibility/booking rules based on these assignments.
"""
import uuid
from django.db import models
from django.conf import settings


class StudentTeacherAssignment(models.Model):
    """
    Mapping of which student is assigned to which teacher for which subject.
    
    Source of truth: PBL System
    
    Rules:
    - One student can have multiple assignments (different subjects, different teachers)
    - Unique constraint: (student, subject) - one teacher per subject per student
    - teacher_external_id is the PBL ID of the teacher
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Student (linked to User model)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignments',
        limit_choices_to={'role': 'student'}
    )
    
    # Teacher external ID from PBL (not a FK - teacher may not exist in scheduler yet)
    teacher_external_id = models.CharField(max_length=255, db_index=True)
    
    # Subject for this assignment
    subject = models.CharField(max_length=100, db_index=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'student_teacher_assignments'
        verbose_name = 'Student-Teacher Assignment'
        verbose_name_plural = 'Student-Teacher Assignments'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'subject'],
                name='unique_student_subject_assignment'
            )
        ]
        indexes = [
            models.Index(fields=['student', 'teacher_external_id']),
            models.Index(fields=['teacher_external_id', 'subject']),
        ]
    
    def __str__(self):
        return f"{self.student.email} -> {self.teacher_external_id} ({self.subject})"
    
    @classmethod
    def get_student_assignments(cls, student):
        """Get all assignments for a student."""
        return cls.objects.filter(student=student)
    
    @classmethod
    def get_assigned_teacher_ids(cls, student):
        """Get list of teacher external IDs assigned to a student."""
        return list(
            cls.objects.filter(student=student)
            .values_list('teacher_external_id', flat=True)
            .distinct()
        )
    
    @classmethod
    def get_assignment_for_subject(cls, student, subject):
        """Get the assignment for a specific student-subject combination."""
        return cls.objects.filter(student=student, subject=subject).first()
    
    @classmethod
    def create_or_update_assignment(cls, student, teacher_external_id, subject):
        """
        Create or update an assignment from SSO data.
        Called during SSO login when assignment data is received.
        """
        assignment, created = cls.objects.update_or_create(
            student=student,
            subject=subject,
            defaults={
                'teacher_external_id': teacher_external_id
            }
        )
        return assignment, created
