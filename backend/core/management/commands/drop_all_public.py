import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = (
        "DANGEROUS: Drops all objects in PostgreSQL public schema (tables/views/sequences) using the configured DATABASE_URL. "
        "Designed for temporary/dev databases."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm you want to drop everything in public schema.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would be dropped, but do not execute.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        yes = bool(options["yes"])

        if connection.vendor != "postgresql":
            self.stderr.write(
                self.style.ERROR(
                    f"Refusing to run: expected PostgreSQL, got {connection.vendor!r}."
                )
            )
            return

        if not settings.DEBUG:
            self.stderr.write(
                self.style.ERROR(
                    "Refusing to run with DEBUG=False. This command is for local/dev databases only."
                )
            )
            return

        if os.getenv("ALLOW_DROP_ALL_PUBLIC") != "1":
            self.stderr.write(
                self.style.ERROR(
                    "Refusing to run without ALLOW_DROP_ALL_PUBLIC=1 in the environment."
                )
            )
            self.stderr.write(
                "Example (PowerShell): `setx ALLOW_DROP_ALL_PUBLIC 1` (new terminal), or `$env:ALLOW_DROP_ALL_PUBLIC='1'` (current session)."
            )
            return

        db_name = connection.settings_dict.get("NAME")
        db_host = connection.settings_dict.get("HOST")
        db_port = connection.settings_dict.get("PORT")
        self.stdout.write(
            f"Target DB (non-sensitive): vendor={connection.vendor} name={db_name!r} host={db_host!r} port={db_port!r}"
        )

        if not dry_run and not yes:
            self.stderr.write(self.style.ERROR("Refusing to run without --yes (or use --dry-run)."))
            return

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 'view' AS kind, table_name AS name
                FROM information_schema.views
                WHERE table_schema = 'public'
                UNION ALL
                SELECT 'table' AS kind, tablename AS name
                FROM pg_tables
                WHERE schemaname = 'public'
                UNION ALL
                SELECT 'sequence' AS kind, sequence_name AS name
                FROM information_schema.sequences
                WHERE sequence_schema = 'public'
                ORDER BY kind, name;
                """
            )
            objects = cursor.fetchall()

        if not objects:
            self.stdout.write(self.style.SUCCESS("No objects found in public schema."))
            return

        self.stdout.write("Objects in public schema:")
        for kind, name in objects:
            self.stdout.write(f"- {kind}: {name}")

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run only; nothing was dropped."))
            return

        dropped = {"view": 0, "table": 0, "sequence": 0}
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DO $$
                DECLARE r RECORD;
                BEGIN
                  -- Drop views first (may depend on tables)
                  FOR r IN (
                    SELECT table_name
                    FROM information_schema.views
                    WHERE table_schema = 'public'
                  ) LOOP
                    EXECUTE 'DROP VIEW IF EXISTS public.' || quote_ident(r.table_name) || ' CASCADE';
                  END LOOP;

                  -- Drop tables
                  FOR r IN (
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                  ) LOOP
                    EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
                  END LOOP;

                  -- Drop sequences (usually already dropped with tables, but keep for completeness)
                  FOR r IN (
                    SELECT sequence_name
                    FROM information_schema.sequences
                    WHERE sequence_schema = 'public'
                  ) LOOP
                    EXECUTE 'DROP SEQUENCE IF EXISTS public.' || quote_ident(r.sequence_name) || ' CASCADE';
                  END LOOP;
                END $$;
                """
            )

        # Recount remaining objects
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.views
                WHERE table_schema = 'public';
                """
            )
            remaining_views = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM pg_tables
                WHERE schemaname = 'public';
                """
            )
            remaining_tables = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.sequences
                WHERE sequence_schema = 'public';
                """
            )
            remaining_sequences = cursor.fetchone()[0]

        self.stdout.write(self.style.SUCCESS("Dropped all objects in public schema."))
        self.stdout.write(f"Remaining views: {remaining_views}")
        self.stdout.write(f"Remaining tables: {remaining_tables}")
        self.stdout.write(f"Remaining sequences: {remaining_sequences}")
