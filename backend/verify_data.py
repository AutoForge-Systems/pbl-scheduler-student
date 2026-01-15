"""
Verification script for test data
Run with: python manage.py shell < verify_data.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scheduler.settings')
django.setup()

from core.models import User
from core.assignment_models import StudentTeacherAssignment
from slots.models import Slot
from django.db.models import Q
from django.utils import timezone

# ============================================
# VERIFICATION: Student-Teacher-Subject Mapping
# ============================================
print('=' * 110)
print('STUDENT-TEACHER-SUBJECT MAPPING')
print('=' * 110)

header = f"{'Student Name':<20} | {'Student Email':<28} | {'Subject':<10} | {'Teacher Name':<20} | {'Teacher PBL ID':<12}"
print(header)
print('-' * 110)

for assignment in StudentTeacherAssignment.objects.all().select_related('student').order_by('student__name', 'subject'):
    student = assignment.student
    teacher = User.objects.filter(pbl_user_id=assignment.teacher_external_id).first()
    teacher_name = teacher.name if teacher else 'NOT FOUND'
    
    row = f"{student.name:<20} | {student.email:<28} | {assignment.subject:<10} | {teacher_name:<20} | {assignment.teacher_external_id:<12}"
    print(row)

# ============================================
# SUMMARY: Teachers and their slots
# ============================================
print()
print('=' * 80)
print('TEACHERS AND SLOTS')
print('=' * 80)

for teacher in User.objects.filter(role='faculty'):
    slots = Slot.objects.filter(faculty=teacher)
    subjects = list(slots.values_list("subject", flat=True).distinct())
    print(f"{teacher.name} ({teacher.pbl_user_id}): {slots.count()} slots | Subjects: {subjects}")

# ============================================
# EXAMPLE: Slots visible to each student
# ============================================
print()
print('=' * 80)
print('SLOTS VISIBLE TO EACH STUDENT')
print('=' * 80)

for student in User.objects.filter(role='student').order_by('name'):
    assignments = StudentTeacherAssignment.objects.filter(student=student)
    
    filters = Q()
    for a in assignments:
        filters |= Q(faculty__pbl_user_id=a.teacher_external_id, subject=a.subject)
    
    if filters:
        visible_slots = Slot.objects.filter(filters, is_available=True, start_time__gt=timezone.now())
        slot_count = visible_slots.count()
    else:
        slot_count = 0
    
    subjects = list(assignments.values_list('subject', flat=True))
    print(f"{student.name}: Can see {slot_count} slots | Assigned subjects: {subjects}")

print()
print('✅ Verification complete!')
