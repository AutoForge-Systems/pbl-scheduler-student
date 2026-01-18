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
        from django.utils import timezone
        from datetime import datetime, time

        # Get today at 7pm (local time)
        now = timezone.localtime()
        today_7pm = timezone.make_aware(datetime.combine(now.date(), time(19, 0)))

        with transaction.atomic():
            # Only delete slots and bookings with start_time <= today at 7pm
            slots_to_delete = Slot.objects.filter(start_time__lte=today_7pm)
            bookings_to_delete = Booking.objects.filter(slot__start_time__lte=today_7pm)

            bookings_count = bookings_to_delete.count()
            slots_count = slots_to_delete.count()
            assignments_count = StudentTeacherAssignment.objects.all().count()

            bookings_to_delete.delete()
            slots_to_delete.delete()
            # Optionally, preserve assignments (remove if you want to reset assignments too)
            # StudentTeacherAssignment.objects.all().delete()

        self.stdout.write(self.style.SUCCESS('Scheduling data reset complete.'))
        self.stdout.write(f'Deleted bookings: {bookings_count}')
        self.stdout.write(f'Deleted slots: {slots_count}')
        self.stdout.write(f'Preserved assignments: {assignments_count}')
