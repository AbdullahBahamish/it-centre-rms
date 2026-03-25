from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = "Validate database, media storage, and migration readiness."

    def handle(self, *args, **options):
        checks = [
            ("Installed apps", self._check_installed_apps),
            ("Migration packages", self._check_migration_packages),
            ("Database connection", self._check_database),
            ("MEDIA_ROOT exists", self._check_media_root),
            ("Migrations applied", self._check_migrations),
            ("Critical schema", self._check_critical_schema),
        ]
        failures = []

        for label, check in checks:
            ok, detail = check()
            status = self.style.SUCCESS("OK") if ok else self.style.ERROR("FAIL")
            self.stdout.write(f"{status} {label}: {detail}")
            if not ok:
                failures.append(label)

        if failures:
            self.stdout.write(self.style.ERROR("System readiness: FAIL"))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("System readiness: OK"))

    @staticmethod
    def _check_database():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as exc:
            return False, str(exc)
        return True, "connected"

    @staticmethod
    def _check_media_root():
        media_root = Path(settings.MEDIA_ROOT)
        if media_root.exists() and media_root.is_dir():
            return True, str(media_root)
        return False, f"missing directory: {media_root}"

    @staticmethod
    def _check_installed_apps():
        required_apps = {"apps.core", "apps.accounts", "apps.records"}
        configured_apps = set(settings.INSTALLED_APPS)
        missing_apps = sorted(required_apps - configured_apps)
        if missing_apps:
            return False, f"missing apps: {', '.join(missing_apps)}"
        return True, "required apps configured"

    @staticmethod
    def _check_migration_packages():
        missing = []
        for app_path in ("apps/accounts", "apps/core", "apps/records"):
            migrations_init = Path(settings.BASE_DIR, app_path, "migrations", "__init__.py")
            if not migrations_init.exists():
                missing.append(str(migrations_init))
        if missing:
            return False, f"missing files: {', '.join(missing)}"
        return True, "migration packages intact"

    @staticmethod
    def _check_migrations():
        try:
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        except Exception as exc:
            return False, str(exc)

        if plan:
            return False, f"{len(plan)} unapplied migration(s)"
        return True, "all applied"

    @staticmethod
    def _check_critical_schema():
        expected_columns = {
            "accounts_userprofile": {"id", "user_id", "phone_number", "role_id"},
            "accounts_role": {"id", "name", "description"},
            "accounts_rolepermission": {
                "id",
                "role_id",
                "can_view_records",
                "can_create_records",
                "can_edit_records",
                "can_delete_records",
                "can_manage_users",
                "can_assign_roles",
            },
        }

        try:
            with connection.cursor() as cursor:
                table_names = set(connection.introspection.table_names(cursor))
                missing_tables = sorted(set(expected_columns) - table_names)
                if missing_tables:
                    return False, f"missing tables: {', '.join(missing_tables)}"

                missing_columns = []
                for table_name, required_columns in expected_columns.items():
                    description = connection.introspection.get_table_description(cursor, table_name)
                    present_columns = {column.name for column in description}
                    absent = sorted(required_columns - present_columns)
                    if absent:
                        missing_columns.append(f"{table_name}: {', '.join(absent)}")
        except Exception as exc:
            return False, str(exc)

        if missing_columns:
            return False, "; ".join(missing_columns)
        return True, "critical tables and columns present"
