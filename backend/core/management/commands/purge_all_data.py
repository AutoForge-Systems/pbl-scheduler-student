from __future__ import annotations

import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection, transaction


class Command(BaseCommand):
    help = (
        "DANGEROUS: Permanently deletes ALL scheduling data from the configured database. "
        "This does NOT drop tables/migrations; it deletes rows."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm deletion (required).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted and row counts, but do not delete.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        yes = bool(options["yes"])

        if connection.vendor != "postgresql":
            self.stderr.write(self.style.ERROR(f"Refusing to run: expected PostgreSQL, got {connection.vendor!r}."))
            return

        # Hard safety gate: must explicitly opt-in.
        if os.getenv("ALLOW_PURGE_ALL_DATA") != "1":
            self.stderr.write(self.style.ERROR("Refusing to run without ALLOW_PURGE_ALL_DATA=1 in the environment."))
            self.stderr.write(
                "PowerShell example: `$env:ALLOW_PURGE_ALL_DATA='1'` (current session)."
            )
            return

        db_name = connection.settings_dict.get("NAME")
        db_host = connection.settings_dict.get("HOST")
        db_port = connection.settings_dict.get("PORT")
        self.stdout.write(
            f"Target DB (non-sensitive): vendor={connection.vendor} name={db_name!r} host={db_host!r} port={db_port!r} DEBUG={settings.DEBUG}"
        )

        if not dry_run and not yes:
            self.stderr.write(self.style.ERROR("Refusing to run without --yes (or use --dry-run)."))
            return

        from bookings.models import Booking, RebookingPermission
        from slots.models import Slot
        from core.models import User
        from core.assignment_models import StudentTeacherAssignment

        # Optional Django tables that contain user/session data.
        from django.contrib.admin.models import LogEntry
        from django.contrib.sessions.models import Session

        # Count rows first
        counts = {
            "bookings": Booking.objects.count(),
            "slots": Slot.objects.count(),
            "rebooking_permissions": RebookingPermission.objects.count(),
            "assignments": StudentTeacherAssignment.objects.count(),
            "admin_log": LogEntry.objects.count(),
            "sessions": Session.objects.count(),
            "users": User.objects.count(),
        }

        self.stdout.write("Row counts to delete:")
        for k, v in counts.items():
            self.stdout.write(f"- {k}: {v}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run only; nothing was deleted."))
            return

        # Delete in FK-safe order
        with transaction.atomic():
            Booking.objects.all().delete()
            Slot.objects.all().delete()
            RebookingPermission.objects.all().delete()
            StudentTeacherAssignment.objects.all().delete()
            LogEntry.objects.all().delete()
            Session.objects.all().delete()
            User.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("ALL DATA PURGED."))
