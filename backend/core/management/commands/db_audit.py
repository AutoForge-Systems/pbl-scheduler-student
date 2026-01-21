from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from datetime import timedelta
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import OperationalError, connection, connections, transaction
from django.utils import timezone


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


class Command(BaseCommand):
    help = (
        "DB audit for production readiness: connection, schema, constraints/indexes, "
        "and a small CRUD/transaction exercise."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--exercise",
            action="store_true",
            help="Run a small create/update/cancel/absent/unlock flow against the live DB (cleans up after).",
        )

    def handle(self, *args, **options):
        results: list[CheckResult] = []

        # 1) Connection & env reality
        results.extend(self._check_connection_and_env())

        # 2) Schema/tables/indexes/fks
        results.extend(self._check_schema())

        # 3) CRUD + transactions
        if options.get("exercise"):
            results.extend(self._exercise_crud_and_transactions())

        self.stdout.write("\n=== SUMMARY ===")
        ok_all = True
        for r in results:
            ok_all = ok_all and r.ok
            label = "OK" if r.ok else "FAIL"
            self.stdout.write(f"[{label}] {r.name}: {r.detail}")

        if ok_all:
            self.stdout.write(self.style.SUCCESS("\nDB AUDIT PASSED"))
        else:
            self.stdout.write(self.style.ERROR("\nDB AUDIT FOUND ISSUES"))

        # Helpful SQL snippets
        self.stdout.write("\n=== MANUAL SQL QUICK CHECKS (public schema) ===")
        self.stdout.write("-- Bookings")
        self.stdout.write("SELECT id, slot_id, student_id, status, absent_at, cancelled_at, created_at FROM public.bookings ORDER BY created_at DESC LIMIT 50;")
        self.stdout.write("\n-- Slots")
        self.stdout.write("SELECT id, faculty_id, subject, start_time, end_time, is_available, created_at FROM public.slots ORDER BY start_time DESC LIMIT 50;")
        self.stdout.write("\n-- Users")
        self.stdout.write("SELECT id, email, role, pbl_user_id, created_at FROM public.users ORDER BY created_at DESC LIMIT 50;")
        self.stdout.write("\n-- Rebooking permissions (""unlock"" records)")
        self.stdout.write("SELECT id, student_id, subject, teacher_external_id, created_at, updated_at FROM public.rebooking_permissions ORDER BY updated_at DESC LIMIT 50;")
        self.stdout.write("\n-- Orphan checks")
        self.stdout.write("SELECT b.id FROM public.bookings b LEFT JOIN public.slots s ON s.id = b.slot_id WHERE s.id IS NULL LIMIT 50;")
        self.stdout.write("SELECT s.id FROM public.slots s LEFT JOIN public.users u ON u.id = s.faculty_id WHERE u.id IS NULL LIMIT 50;")

    def _check_connection_and_env(self) -> list[CheckResult]:
        out: list[CheckResult] = []
        try:
            conn = connections["default"]
            conn.ensure_connection()
        except OperationalError as e:
            return [CheckResult("DB connection", False, f"Cannot connect: {e}")]

        s = conn.settings_dict
        vendor = conn.vendor
        engine = s.get("ENGINE")
        host = s.get("HOST")
        name = s.get("NAME")
        user = s.get("USER")
        opts = s.get("OPTIONS") or {}

        out.append(CheckResult("DB vendor", vendor == "postgresql", f"vendor={vendor}"))
        out.append(CheckResult("DB engine", engine == "django.db.backends.postgresql", f"ENGINE={engine}"))

        using_sqlite_fallback = engine == "django.db.backends.sqlite3"
        out.append(
            CheckResult(
                "No SQLite fallback",
                not using_sqlite_fallback,
                "Using PostgreSQL" if not using_sqlite_fallback else "Using SQLite fallback (DATABASE_URL missing?)",
            )
        )

        sslmode = (opts.get("sslmode") or "").lower()
        # Supabase hosts should be SSL-required
        if host and "supabase" in str(host).lower():
            out.append(CheckResult("SSL mode", sslmode == "require", f"sslmode={sslmode or 'unset'} (host={host})"))
        else:
            out.append(CheckResult("SSL mode", True, f"sslmode={sslmode or 'unset'} (host={host})"))

        out.append(CheckResult("Env DEBUG", True, f"DEBUG={settings.DEBUG}"))
        out.append(CheckResult("Env SSO_MODE", True, f"SSO_MODE={getattr(settings, 'SSO_MODE', None)}"))
        out.append(CheckResult("Env PBL_API_URL set", bool(getattr(settings, "PBL_API_URL", "")), f"PBL_API_URL_SET={bool(getattr(settings, 'PBL_API_URL', ''))}"))
        out.append(CheckResult("Env PBL_API_KEY set", bool(getattr(settings, "PBL_API_KEY", "")), f"PBL_API_KEY_SET={bool(getattr(settings, 'PBL_API_KEY', ''))}"))

        out.append(
            CheckResult(
                "DB settings",
                True,
                f"HOST={host} NAME={name} USER={user} OPTIONS={opts}",
            )
        )

        return out

    def _fetchall_dict(self, sql: str, params=None) -> list[dict]:
        with connection.cursor() as cursor:
            cursor.execute(sql, params or [])
            cols = [c[0] for c in cursor.description]
            return [dict(zip(cols, row)) for row in cursor.fetchall()]

    def _check_schema(self) -> list[CheckResult]:
        out: list[CheckResult] = []

        # List tables in public
        tables = self._fetchall_dict(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name;
            """
        )
        table_names = [t["table_name"] for t in tables]

        expected = [
            "users",
            "slots",
            "bookings",
            "rebooking_permissions",
            # Django internals
            "django_migrations",
            "django_content_type",
            "django_admin_log",
            "django_session",
        ]

        for t in expected:
            out.append(CheckResult(f"Table exists: {t}", t in table_names, "present" if t in table_names else "missing"))

        # Column/type/nullable checks for core tables
        out.extend(self._check_table_columns("users", {
            "id": ("uuid", False),
            "email": ("character varying", False),
            "name": ("character varying", False),
            "role": ("character varying", False),
            "pbl_user_id": ("character varying", True),
        }))

        out.extend(self._check_table_columns("slots", {
            "id": ("uuid", False),
            "faculty_id": ("uuid", False),
            "subject": ("character varying", False),
            "start_time": ("timestamp with time zone", False),
            "end_time": ("timestamp with time zone", False),
            "is_available": ("boolean", False),
        }))

        out.extend(self._check_table_columns("bookings", {
            "id": ("uuid", False),
            "slot_id": ("uuid", False),
            "student_id": ("uuid", False),
            "status": ("character varying", False),
            "absent_at": ("timestamp with time zone", True),
            "cancelled_at": ("timestamp with time zone", True),
        }))

        out.extend(self._check_table_columns("rebooking_permissions", {
            "id": ("uuid", False),
            "student_id": ("uuid", False),
            "subject": ("character varying", False),
            "teacher_external_id": ("character varying", False),
        }))

        # Index + FK presence checks
        out.extend(self._check_indexes_and_fks())
        out.extend(self._check_orphans())

        return out

    def _check_table_columns(self, table: str, expected: dict[str, tuple[str, bool]]) -> list[CheckResult]:
        out: list[CheckResult] = []
        rows = self._fetchall_dict(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position;
            """,
            [table],
        )
        if not rows:
            return [CheckResult(f"Columns: {table}", False, "table not found or no columns")]

        cols = {r["column_name"]: r for r in rows}
        for col, (dtype, nullable) in expected.items():
            if col not in cols:
                out.append(CheckResult(f"Column {table}.{col}", False, "missing"))
                continue

            actual_dtype = cols[col]["data_type"]
            actual_nullable = (cols[col]["is_nullable"] == "YES")
            dtype_ok = (actual_dtype == dtype)
            nullable_ok = (actual_nullable == nullable)

            ok = dtype_ok and nullable_ok
            out.append(
                CheckResult(
                    f"Column {table}.{col}",
                    ok,
                    f"type={actual_dtype} nullable={actual_nullable}",
                )
            )

        return out

    def _check_indexes_and_fks(self) -> list[CheckResult]:
        out: list[CheckResult] = []

        idx_rows = self._fetchall_dict(
            """
            SELECT tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname='public' AND tablename IN ('users','slots','bookings','rebooking_permissions')
            ORDER BY tablename, indexname;
            """
        )

        indexes_by_table: dict[str, list[str]] = {}
        for r in idx_rows:
            indexes_by_table.setdefault(r["tablename"], []).append(r["indexdef"].lower())

        def has_index(table: str, needle: str) -> bool:
            return any(needle.lower() in idx for idx in indexes_by_table.get(table, []))

        # users
        out.append(CheckResult("Index users(email)", has_index("users", "(email)"), "email index/unique"))
        out.append(CheckResult("Index users(pbl_user_id)", has_index("users", "(pbl_user_id)"), "pbl_user_id index"))

        # slots
        out.append(CheckResult("Index slots(subject)", has_index("slots", "(subject)"), "subject index"))
        out.append(CheckResult("Index slots(start_time)", has_index("slots", "(start_time)"), "start_time index"))
        out.append(CheckResult("Index slots(faculty_id,start_time)", has_index("slots", "(faculty_id, start_time)"), "composite index"))

        # bookings
        out.append(CheckResult("Index bookings(student_id,status)", has_index("bookings", "(student_id, status)"), "composite index"))
        out.append(CheckResult("Index bookings(status,created_at)", has_index("bookings", "(status, created_at)"), "composite index"))
        out.append(CheckResult("Index bookings(absent_at)", has_index("bookings", "(absent_at)"), "absent_at index"))
        out.append(CheckResult("Unique booking slot_id", has_index("bookings", "unique") and has_index("bookings", "(slot_id)"), "one-to-one slot booking"))

        # rebooking_permissions
        out.append(CheckResult("Unique rebooking_permissions(student_id,subject)", has_index("rebooking_permissions", "unique") and has_index("rebooking_permissions", "(student_id, subject)"), "unique constraint"))

        # FK constraints
        fk_rows = self._fetchall_dict(
            """
            SELECT
              conrelid::regclass::text AS table_name,
              confrelid::regclass::text AS referenced_table,
              conname,
              pg_get_constraintdef(c.oid) AS def
            FROM pg_constraint c
            WHERE contype='f'
              AND connamespace = 'public'::regnamespace
            ORDER BY table_name, conname;
            """
        )

        def _strip_schema(name: str) -> str:
            # regclass::text may return 'public.table'
            return (name or '').split('.')[-1].strip('"')

        fk_pairs = set(
            (_strip_schema(r["table_name"]), _strip_schema(r["referenced_table"]))
            for r in fk_rows
        )

        out.append(CheckResult(
            "FK slots.faculty_id -> users",
            ("slots", "users") in fk_pairs,
            "checked in pg_constraint",
        ))
        out.append(CheckResult(
            "FK bookings.slot_id -> slots",
            ("bookings", "slots") in fk_pairs,
            "checked in pg_constraint",
        ))
        out.append(CheckResult(
            "FK bookings.student_id -> users",
            ("bookings", "users") in fk_pairs,
            "checked in pg_constraint",
        ))
        out.append(CheckResult(
            "FK rebooking_permissions.student_id -> users",
            ("rebooking_permissions", "users") in fk_pairs,
            "checked in pg_constraint",
        ))

        return out

    def _check_orphans(self) -> list[CheckResult]:
        out: list[CheckResult] = []

        orphan_bookings = self._fetchall_dict(
            """
            SELECT b.id
            FROM public.bookings b
            LEFT JOIN public.slots s ON s.id = b.slot_id
            WHERE s.id IS NULL
            LIMIT 1;
            """
        )
        out.append(CheckResult("No orphan bookings (booking without slot)", len(orphan_bookings) == 0, "none" if not orphan_bookings else "found"))

        orphan_slots = self._fetchall_dict(
            """
            SELECT s.id
            FROM public.slots s
            LEFT JOIN public.users u ON u.id = s.faculty_id
            WHERE u.id IS NULL
            LIMIT 1;
            """
        )
        out.append(CheckResult("No orphan slots (slot without faculty)", len(orphan_slots) == 0, "none" if not orphan_slots else "found"))

        return out

    def _exercise_crud_and_transactions(self) -> list[CheckResult]:
        out: list[CheckResult] = []

        if not settings.DEBUG and os.environ.get('DB_AUDIT_ALLOW_WRITE') != '1':
            return [
                CheckResult(
                    "Exercise mode enabled",
                    False,
                    "Refusing to write in production. Set DB_AUDIT_ALLOW_WRITE=1 if you really intend to run this.",
                )
            ]

        from bookings.models import Booking, RebookingPermission
        from core.models import User
        from slots.models import Slot
        from core.subjects import ALLOWED_SUBJECTS

        # Create two students and one faculty + two slots.
        suffix = uuid.uuid4().hex[:10]
        faculty = User.objects.create_user(
            email=f"__db_audit_faculty_{suffix}@example.com",
            name="DB Audit Faculty",
            role="faculty",
            pbl_user_id=f"db_audit_faculty_{suffix}",
        )
        student1 = User.objects.create_user(
            email=f"__db_audit_student1_{suffix}@example.com",
            name="DB Audit Student 1",
            role="student",
            pbl_user_id=f"db_audit_student1_{suffix}",
        )
        student2 = User.objects.create_user(
            email=f"__db_audit_student2_{suffix}@example.com",
            name="DB Audit Student 2",
            role="student",
            pbl_user_id=f"db_audit_student2_{suffix}",
        )

        subject = sorted(ALLOWED_SUBJECTS)[0]
        now = timezone.now()
        slot1 = Slot.objects.create(
            faculty=faculty,
            subject=subject,
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, minutes=10),
            is_available=True,
        )
        slot2 = Slot.objects.create(
            faculty=faculty,
            subject=subject,
            start_time=now + timedelta(days=1, minutes=20),
            end_time=now + timedelta(days=1, minutes=30),
            is_available=True,
        )

        # Persistence: ensure rows survive new DB connection.
        created_slot_id = str(slot1.id)
        connections.close_all()
        found = Slot.objects.filter(id=created_slot_id).exists()
        out.append(CheckResult("Persistence (slot survives reconnect)", found, f"slot_id={created_slot_id}"))

        # Student/subject booking rule: only one CONFIRMED per (student, subject)
        b1 = Booking.create_booking(slot1, student1)
        out.append(CheckResult("Booking insert", Booking.objects.filter(id=b1.id).exists(), f"booking_id={b1.id} status={b1.status}"))

        try:
            Booking.create_booking(slot2, student2)
            out.append(CheckResult("Per-student subject uniqueness", True, "different student booking allowed"))
        except Exception:
            out.append(CheckResult("Per-student subject uniqueness", False, "different student booking was blocked"))

        # Cancellation restores slot availability
        b1.cancel(reason="db audit cancel", force=True)
        slot1.refresh_from_db()
        out.append(CheckResult("Cancel updates DB", slot1.is_available is True and b1.status == Booking.Status.CANCELLED, f"slot_available={slot1.is_available} status={b1.status}"))

        # Absence lock is per-student and blocks until permission updated
        b2 = Booking.create_booking(slot2, student1)
        b2.status = Booking.Status.ABSENT
        b2.absent_at = timezone.now()
        b2.save(update_fields=["status", "absent_at", "updated_at"])

        # Create a fresh slot for rebook attempt
        slot3 = Slot.objects.create(
            faculty=faculty,
            subject=subject,
            start_time=now + timedelta(days=2),
            end_time=now + timedelta(days=2, minutes=10),
            is_available=True,
        )

        # First attempt should be blocked
        try:
            Booking.create_booking(slot3, student1)
            out.append(CheckResult("Absent lock blocks rebook", False, "rebook succeeded without permission"))
        except Exception:
            out.append(CheckResult("Absent lock blocks rebook", True, "rebook blocked"))

        # Allow rebooking: create/update permission
        RebookingPermission.objects.update_or_create(
            student=student1,
            subject=subject,
            defaults={"teacher_external_id": faculty.pbl_user_id},
        )

        slot4 = Slot.objects.create(
            faculty=faculty,
            subject=subject,
            start_time=now + timedelta(days=2, minutes=20),
            end_time=now + timedelta(days=2, minutes=30),
            is_available=True,
        )

        try:
            b3 = Booking.create_booking(slot4, student1)
            out.append(CheckResult("Unlock allows rebook", b3.status == Booking.Status.CONFIRMED, f"booking_id={b3.id}"))
        except Exception as e:
            out.append(CheckResult("Unlock allows rebook", False, f"failed: {e}"))

        # Concurrency: two students racing for same slot (new slot)
        slot_race = Slot.objects.create(
            faculty=faculty,
            subject=subject,
            start_time=now + timedelta(days=3),
            end_time=now + timedelta(days=3, minutes=10),
            is_available=True,
        )

        barrier = threading.Barrier(2)
        race_results: list[str] = []

        def attempt(student: User):
            from django.db import close_old_connections

            close_old_connections()
            barrier.wait()
            try:
                Booking.create_booking(slot_race, student)
                race_results.append("ok")
            except Exception:
                race_results.append("fail")

        t1 = threading.Thread(target=attempt, args=(student1,))
        t2 = threading.Thread(target=attempt, args=(student2,))
        t1.start(); t2.start(); t1.join(); t2.join()

        out.append(CheckResult("Concurrency (only one booking wins)", sorted(race_results) == ["fail", "ok"], f"results={race_results}"))

        # Cleanup (best-effort)
        Booking.objects.filter(student__email__startswith="__db_audit_").delete()
        Slot.objects.filter(faculty__email__startswith="__db_audit_").delete()
        RebookingPermission.objects.filter(student__email__startswith="__db_audit_").delete()
        User.objects.filter(email__startswith="__db_audit_").delete()

        return out
