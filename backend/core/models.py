"""
Core Models - User Model for Scheduler
"""
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models

# Import assignment model so it's picked up by migrations
from core.assignment_models import StudentTeacherAssignment


class UserManager(BaseUserManager):
    """Custom manager for User model."""
    
    def create_user(self, email, name, role, password=None, **extra_fields):
        """Create and return a regular user."""
        if not email:
            raise ValueError('Email is required')
        if not role:
            raise ValueError('Role is required')
        
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, role=role, **extra_fields)
        
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, name, password=None, **extra_fields):
        """Create and return a superuser."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        return self.create_user(
            email=email,
            name=name,
            role='faculty',
            password=password,
            **extra_fields
        )


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for the Scheduler.
    Users are created/updated via SSO from PBL platform.
    """
    
    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        FACULTY = 'faculty', 'Faculty'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=Role.choices)
    
    # PBL integration field - stores external user ID from PBL
    pbl_user_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    # Faculty availability status (only used for faculty role)
    # True = Available/Free, False = Busy
    is_available_for_booking = models.BooleanField(default=True)
    
    # Django required fields
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.email})"
    
    @property
    def is_student(self):
        return self.role == self.Role.STUDENT
    
    @property
    def is_faculty(self):
        return self.role == self.Role.FACULTY
