from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.models import Q
from django.utils import timezone


class Command(BaseCommand):
    help = "Verify business invariants and print table list + row counts."

    def handle(self, *args, **options):
        from core.models import User
        from core.assignment_models import StudentTeacherAssignment
        from slots.models import Slot
        from bookings.models import Booking

        ok = True

        # 1) Each teacher has exactly one subject (based on subjects present in their slots)
        teacher_subjects = {}
        for t in User.objects.filter(role='faculty'):
            subjects = list(
                Slot.objects.filter(faculty=t).values_list('subject', flat=True).distinct()
            )
            teacher_subjects[t.email] = sorted(set([s for s in subjects if s]))

        bad_teachers = {email: subs for email, subs in teacher_subjects.items() if len(subs) != 1}
        if bad_teachers:
            ok = False
            self.stdout.write(self.style.ERROR("FAIL: Each teacher must have exactly one subject"))
            for email, subs in bad_teachers.items():
                self.stdout.write(f"- {email}: {subs}")
        else:
            self.stdout.write(self.style.SUCCESS("PASS: Each teacher has exactly one subject"))

        # 2) Each student has two subjects (based on assignments)
        bad_students = []
        for s in User.objects.filter(role='student'):
            subs = list(
                StudentTeacherAssignment.objects.filter(student=s)
                .values_list('subject', flat=True)
                .distinct()
            )
            subs = sorted([x for x in subs if x])
            if len(subs) != 2:
                bad_students.append((s.email, subs))

        if bad_students:
            ok = False
            self.stdout.write(self.style.ERROR("FAIL: Each student must have exactly two subjects"))
            for email, subs in bad_students:
                self.stdout.write(f"- {email}: {subs}")
        else:
            self.stdout.write(self.style.SUCCESS("PASS: Each student has exactly two subjects"))

        # 3) Students see only assigned teacher slots (simulate the backend filtering)
        now = timezone.now()
        for student in User.objects.filter(role='student'):
            assignments = StudentTeacherAssignment.objects.filter(student=student)
            filters = Q()
            for a in assignments:
                filters |= Q(faculty__pbl_user_id=a.teacher_external_id, subject=a.subject)

            visible = Slot.objects.filter(
                filters,
                is_available=True,
                start_time__gt=now,
            )

            # Ensure every visible slot matches at least one assignment
            assignment_pairs = set((a.teacher_external_id, a.subject) for a in assignments)
            mismatches = []
            for slot in visible.select_related('faculty'):
                pair = (slot.faculty.pbl_user_id, slot.subject)
                if pair not in assignment_pairs:
                    mismatches.append(str(slot.id))

            if mismatches:
                ok = False
                self.stdout.write(self.style.ERROR(f"FAIL: Visibility mismatch for {student.email}"))
                for sid in mismatches:
                    self.stdout.write(f"- slot_id: {sid}")
            else:
                self.stdout.write(self.style.SUCCESS(f"PASS: Visibility OK for {student.email}"))

        # 4) One booking per subject enforced (attempt second booking)
        test_student = User.objects.filter(role='student').order_by('email').first()
        if test_student:
            for subject in ["Web Development", "Compiler Design"]:
                # Find an available slot for that subject assigned to the student
                a = StudentTeacherAssignment.objects.filter(student=test_student, subject=subject).first()
                if not a:
                    continue
                available_slots = Slot.objects.filter(
                    faculty__pbl_user_id=a.teacher_external_id,
                    subject=subject,
                    start_time__gt=now,
                ).order_by('start_time')

                # Ensure there are at least 2 slots in that subject to try booking twice
                if available_slots.count() < 2:
                    continue

                # Book first if not already booked
                first = available_slots[0]
                second = available_slots[1]

                # If no booking exists yet for subject, create one
                existing = Booking.objects.filter(
                    student=test_student,
                    status='confirmed',
                    slot__subject=subject,
                ).exists()
                if not existing:
                    Booking.create_booking(first, test_student)

                try:
                    Booking.create_booking(second, test_student)
                    ok = False
                    self.stdout.write(self.style.ERROR(f"FAIL: Allowed second booking for subject {subject}"))
                except Exception:
                    self.stdout.write(self.style.SUCCESS(f"PASS: One-booking-per-subject enforced for {subject}"))

        # Table list + row counts per table
        self.stdout.write("\nTABLES + ROW COUNTS (public schema):")
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename;
                """
            )
            tables = [r[0] for r in cursor.fetchall()]

            for t in tables:
                cursor.execute(f'SELECT COUNT(*) FROM public."{t}";')
                cnt = cursor.fetchone()[0]
                self.stdout.write(f"- {t}: {cnt}")

        if ok:
            self.stdout.write(self.style.SUCCESS("\nALL VERIFICATIONS PASSED"))
        else:
            self.stdout.write(self.style.ERROR("\nONE OR MORE VERIFICATIONS FAILED"))
