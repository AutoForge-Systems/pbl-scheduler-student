from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = "Seed deterministic dummy data (users, assignments, slots, bookings) for dev/testing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm seeding. This will delete existing rows in scheduler tables.",
        )

    def handle(self, *args, **options):
        if not options["yes"]:
            self.stderr.write(self.style.ERROR("Refusing to run without --yes"))
            return

        from core.models import User
        from core.assignment_models import StudentTeacherAssignment
        from slots.models import Slot
        from bookings.models import Booking

        subjects = ["Web Development", "Compiler Design"]

        with transaction.atomic():
            # Clear in FK-safe order
            Booking.objects.all().delete()
            Slot.objects.all().delete()
            StudentTeacherAssignment.objects.all().delete()
            User.objects.all().delete()

            # Faculty (each has exactly one subject via the slots we create)
            faculty_web = User.objects.create_user(
                email="faculty.web@example.com",
                name="Faculty Web",
                role="faculty",
                password="dev",
                pbl_user_id="FAC_WEB",
                is_available_for_booking=True,
            )
            faculty_comp = User.objects.create_user(
                email="faculty.compiler@example.com",
                name="Faculty Compiler",
                role="faculty",
                password="dev",
                pbl_user_id="FAC_COMP",
                is_available_for_booking=True,
            )
            # Extra faculty not assigned to any student (to validate visibility)
            faculty_unassigned = User.objects.create_user(
                email="faculty.unassigned@example.com",
                name="Faculty Unassigned",
                role="faculty",
                password="dev",
                pbl_user_id="FAC_UNUSED",
                is_available_for_booking=True,
            )

            # Students (each has two subjects)
            students = []
            for idx in range(1, 4):
                students.append(
                    User.objects.create_user(
                        email=f"student{idx}@example.com",
                        name=f"Student {idx}",
                        role="student",
                        password="dev",
                        pbl_user_id=f"STU_{idx}",
                    )
                )

            # Assignments: each student has exactly two subjects
            for student in students:
                StudentTeacherAssignment.objects.create(
                    student=student,
                    teacher_external_id=faculty_web.pbl_user_id,
                    subject="Web Development",
                )
                StudentTeacherAssignment.objects.create(
                    student=student,
                    teacher_external_id=faculty_comp.pbl_user_id,
                    subject="Compiler Design",
                )

            # Slots for each faculty (future)
            base = timezone.now() + timedelta(days=1)

            def make_slots(faculty: User, subject: str, start_hour: int):
                slots = []
                for i in range(3):
                    start = base.replace(hour=start_hour, minute=0, second=0, microsecond=0) + timedelta(minutes=20 * i)
                    end = start + timedelta(minutes=10)
                    slots.append(
                        Slot.objects.create(
                            faculty=faculty,
                            subject=subject,
                            start_time=start,
                            end_time=end,
                            is_available=True,
                        )
                    )
                return slots

            web_slots = make_slots(faculty_web, "Web Development", 10)
            comp_slots = make_slots(faculty_comp, "Compiler Design", 12)
            _unused_slots = make_slots(faculty_unassigned, "Web Development", 14)

            # Bookings: Student 1 books one per subject
            Booking.create_booking(web_slots[0], students[0])
            Booking.create_booking(comp_slots[0], students[0])

        self.stdout.write(self.style.SUCCESS("Seeded dummy data successfully."))
        self.stdout.write(f"Faculty: {User.objects.filter(role='faculty').count()}")
        self.stdout.write(f"Students: {User.objects.filter(role='student').count()}")
        self.stdout.write(f"Assignments: {StudentTeacherAssignment.objects.count()}")
        self.stdout.write(f"Slots: {Slot.objects.count()}")
        self.stdout.write(f"Bookings: {Booking.objects.count()}")
