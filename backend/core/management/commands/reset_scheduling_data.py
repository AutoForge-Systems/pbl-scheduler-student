from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'DEV ONLY: Reset scheduling data (bookings, slots, assignments).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Confirm deletion (required).',
        )

    def handle(self, *args, **options):
        if not options['yes']:
            self.stderr.write(self.style.ERROR('Refusing to run without --yes'))
            return

        from bookings.models import Booking
        from slots.models import Slot
        from core.assignment_models import StudentTeacherAssignment

        with transaction.atomic():
            bookings_count = Booking.objects.all().count()
            slots_count = Slot.objects.all().count()
            assignments_count = StudentTeacherAssignment.objects.all().count()

            Booking.objects.all().delete()
            Slot.objects.all().delete()
            StudentTeacherAssignment.objects.all().delete()

        self.stdout.write(self.style.SUCCESS('Scheduling data reset complete.'))
        self.stdout.write(f'Deleted bookings: {bookings_count}')
        self.stdout.write(f'Deleted slots: {slots_count}')
        self.stdout.write(f'Deleted assignments: {assignments_count}')
