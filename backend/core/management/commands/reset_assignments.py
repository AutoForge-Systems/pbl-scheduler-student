from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError

from core.assignment_models import StudentTeacherAssignment


class Command(BaseCommand):
    help = 'Delete all StudentTeacherAssignment rows (subject-wise student↔faculty/evaluator mappings).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Confirm deletion without prompting.',
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Also clear Django cache (optional).',
        )

    def handle(self, *args, **options):
        if not options.get('yes'):
            raise CommandError('Refusing to delete assignments without --yes')

        deleted_count, _ = StudentTeacherAssignment.objects.all().delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} StudentTeacherAssignment rows.'))

        if options.get('clear_cache'):
            cache.clear()
            self.stdout.write(self.style.SUCCESS('Cleared Django cache.'))