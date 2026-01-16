from __future__ import annotations

from typing import Any, Dict, List

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Sync faculty users from the external PBL API into the local users table. "
        "Upserts by email and sets role='faculty' and pbl_user_id."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change, but do not write to the database.",
        )
        parser.add_argument(
            "--deactivate-missing",
            action="store_true",
            help=(
                "Mark local faculty users as inactive if their email is not present in the PBL faculty list. "
                "(Safe default is to NOT deactivate.)"
            ),
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        deactivate_missing = bool(options["deactivate_missing"])

        from core.models import User
        from core.pbl_external import get_faculty

        if (getattr(settings, "SSO_MODE", "") or "").lower() == "mock":
            self.stderr.write(
                self.style.WARNING(
                    "SSO_MODE is 'mock'. In mock mode, get_faculty() reads local DB users instead of calling PBL. "
                    "Set SSO_MODE=real and configure PBL_API_URL/PBL_API_KEY to sync from production PBL."
                )
            )

        if not getattr(settings, "PBL_API_URL", "") or not getattr(settings, "PBL_API_KEY", ""):
            self.stderr.write(
                self.style.WARNING(
                    "PBL_API_URL / PBL_API_KEY not configured in this environment; external PBL sync cannot run here."
                )
            )

        faculty: List[Dict[str, Any]] = get_faculty()

        if not isinstance(faculty, list) or not faculty:
            self.stderr.write(self.style.ERROR("No faculty returned from PBL faculty source."))
            self.stderr.write(
                "If you expected PBL data, run this command where SSO_MODE=real and PBL_API_URL/PBL_API_KEY are set."
            )
            return

        cleaned: List[Dict[str, str]] = []
        skipped = 0
        for raw in faculty:
            if not isinstance(raw, dict):
                skipped += 1
                continue

            email = (raw.get("email") or "").strip().lower()
            name = (raw.get("name") or "").strip()
            pbl_id = raw.get("id") or raw.get("pbl_user_id")
            pbl_id = str(pbl_id).strip() if pbl_id is not None else ""

            if not email or not pbl_id:
                skipped += 1
                continue

            if not name:
                name = email.split("@")[0]

            cleaned.append({"email": email, "name": name, "pbl_user_id": pbl_id})

        if not cleaned:
            self.stderr.write(self.style.ERROR("No valid faculty records after cleaning."))
            return

        # Deduplicate by email (PBL should be unique but don't trust it)
        by_email: Dict[str, Dict[str, str]] = {}
        for row in cleaned:
            by_email[row["email"]] = row

        target_emails = set(by_email.keys())

        created = 0
        updated = 0

        self.stdout.write(
            f"PBL faculty fetched: {len(faculty)} | valid: {len(by_email)} | skipped: {skipped} | dry_run={dry_run}"
        )

        def upsert_one(row: Dict[str, str]):
            nonlocal created, updated
            obj, was_created = User.objects.update_or_create(
                email=row["email"],
                defaults={
                    "name": row["name"],
                    "role": "faculty",
                    "pbl_user_id": row["pbl_user_id"],
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
            return obj

        if dry_run:
            # Estimate what would happen
            existing = set(User.objects.filter(email__in=target_emails).values_list("email", flat=True))
            created = len(target_emails - existing)
            updated = len(existing)
            self.stdout.write(self.style.WARNING("Dry-run only; no DB writes."))
            self.stdout.write(f"Would create: {created}")
            self.stdout.write(f"Would update: {updated}")
            if deactivate_missing:
                would_deactivate = User.objects.filter(role="faculty").exclude(email__in=target_emails).count()
                self.stdout.write(f"Would deactivate missing faculty: {would_deactivate}")
            return

        with transaction.atomic():
            for row in by_email.values():
                upsert_one(row)

            deactivated = 0
            if deactivate_missing:
                deactivated = (
                    User.objects.filter(role="faculty").exclude(email__in=target_emails).update(is_active=False)
                )

        self.stdout.write(self.style.SUCCESS("Faculty sync completed."))
        self.stdout.write(f"Created: {created}")
        self.stdout.write(f"Updated: {updated}")
        if deactivate_missing:
            self.stdout.write(f"Deactivated missing: {deactivated}")
