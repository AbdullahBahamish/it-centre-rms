from unittest.mock import patch
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.accounts.bootstrap import bootstrap_roles_and_permissions
from apps.accounts.models import Role, UserProfile
from apps.core.middleware import AccessPolicyMiddleware, AuthRateLimitMiddleware, is_exempt
from apps.core.models import SystemSettings
from apps.core.rbac import get_user_role, normalize_role_code, validate_role_codes
from apps.core.security import ServiceResult, with_retry
from apps.core.services import AccessService
from apps.core.validators import validate_serial_number
from apps.records.models import Category, Record, RecordType


User = get_user_model()


def set_role(user, role_name):
    UserProfile.objects.filter(user=user).update(role=Role.objects.get(name=role_name))
    user.refresh_from_db()
    return user


class RoleAndValidationTests(TestCase):
    def test_normalizes_legacy_role_codes(self):
        self.assertEqual(normalize_role_code("engineer"), Role.STAFF)
        self.assertEqual(normalize_role_code("ADMIN"), Role.ADMIN)
        self.assertIsNone(normalize_role_code(""))

    def test_validates_role_code_lists(self):
        validate_role_codes(["admin", Role.STAFF])

        with self.assertRaisesMessage(ValidationError, "Roles must be a list"):
            validate_role_codes("ADMIN")
        with self.assertRaisesMessage(ValidationError, "Invalid roles: UNKNOWN"):
            validate_role_codes(["UNKNOWN"])

    def test_serial_number_validator_accepts_expected_format(self):
        validate_serial_number("AB-123456")

        with self.assertRaisesMessage(ValidationError, "Invalid serial number format"):
            validate_serial_number("invalid serial")


class SecurityUtilityTests(TestCase):
    def test_retry_returns_value_after_transient_database_error(self):
        operation = patch("apps.core.security.time.sleep").start()
        self.addCleanup(patch.stopall)
        calls = 0

        def eventually_succeeds():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OperationalError("locked")
            return "completed"

        self.assertEqual(with_retry(eventually_succeeds, retries=2), "completed")
        self.assertEqual(calls, 2)
        operation.assert_called_once()

    def test_retry_returns_conflict_after_last_database_error(self):
        result = with_retry(lambda: (_ for _ in ()).throw(OperationalError("locked")), retries=1)

        self.assertEqual(result, ServiceResult(success=False, error="deadlock", status_code=409))


class AccessServiceTests(TestCase):
    def setUp(self):
        bootstrap_roles_and_permissions()
        self.admin = set_role(User.objects.create_user("admin", password="StrongPass123!"), Role.ADMIN)
        self.manager = set_role(User.objects.create_user("manager", password="StrongPass123!"), Role.MANAGER)
        self.staff = set_role(User.objects.create_user("staff", password="StrongPass123!"), Role.STAFF)
        self.viewer = set_role(User.objects.create_user("viewer", password="StrongPass123!"), Role.VIEWER)
        self.category = Category.objects.create(name="Restricted", allowed_roles=[Role.STAFF])
        self.record = Record.objects.create(
            title="Router repair",
            record_type=RecordType.objects.create(name="Maintenance"),
            category=self.category,
            created_by=self.staff,
        )

    def test_category_access_honours_role_and_explicit_user_grant(self):
        self.assertTrue(AccessService.can(self.staff, "access_category", self.category))
        self.assertFalse(AccessService.can(self.viewer, "access_category", self.category))

        self.category.allowed_users.add(self.viewer)
        self.assertTrue(AccessService.can(self.viewer, "access_category", self.category))

    def test_record_permissions_apply_ownership_and_role_hierarchy(self):
        self.assertTrue(AccessService.can(self.staff, "view_record", self.record))
        self.assertTrue(AccessService.can(self.staff, "update_record", self.record))
        self.assertTrue(AccessService.can(self.staff, "delete_record", self.record))
        self.assertFalse(AccessService.can(self.viewer, "view_record", self.record))
        self.manager.userprofile.role.permissions.can_edit_records = True
        self.manager.userprofile.role.permissions.save(update_fields=["can_edit_records"])
        self.category.allowed_users.add(self.manager)
        self.assertTrue(AccessService.can(self.manager, "update_record", self.record))
        self.assertTrue(AccessService.can(self.admin, "delete_record", self.record))

    def test_role_helpers_resolve_current_role(self):
        self.assertEqual(get_user_role(self.manager), Role.MANAGER)
        self.assertEqual(AccessService.get_role_name(None), AccessService.ANONYMOUS_ROLE_NAME)

    def test_django_superuser_resolves_to_rms_admin_role(self):
        superuser = User.objects.create_superuser("django-admin", password="StrongPass123!")

        self.assertEqual(AccessService.get_role_name(superuser), Role.ADMIN)
        self.assertTrue(AccessService.can(superuser, "access_admin_panel"))


@override_settings(SECURE_SSL_REDIRECT=False)
class CoreRequestTests(TestCase):
    def test_health_check_reports_database_availability(self):
        response = self.client.get(reverse("health_check"))

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok", "database": True})

    def test_system_settings_remains_a_singleton(self):
        settings = SystemSettings.get_solo()
        duplicate = SystemSettings(require_login=False)
        duplicate.save()

        self.assertEqual(SystemSettings.objects.count(), 1)
        self.assertEqual(duplicate.pk, settings.pk)
        settings.refresh_from_db()
        self.assertFalse(settings.require_login)

    def test_exempt_paths_are_limited_to_public_endpoints(self):
        self.assertTrue(is_exempt("/health/"))
        self.assertTrue(is_exempt("/accounts/reset/uid/token/"))
        self.assertFalse(is_exempt("/records/"))

    def test_access_policy_allows_configured_anonymous_read_only_requests(self):
        middleware = AccessPolicyMiddleware(lambda request: self.client.get(reverse("health_check")))
        request = RequestFactory().get("/records/")
        request.user = type("Anonymous", (), {"is_authenticated": False})()

        with override_settings(ACCESS_DENIED_STATUS_CODE=403), patch.object(
            AccessPolicyMiddleware,
            "_get_system_settings",
            return_value={
                "require_login": False,
                "allow_anonymous_view": True,
                "allow_anonymous_create": False,
                "allow_anonymous_update": False,
                "allow_anonymous_delete": False,
            },
        ):
            response = middleware(request)

        self.assertEqual(response.status_code, 200)

    def test_rate_limit_uses_authenticated_identity(self):
        user = User.objects.create_user("rate-user", password="StrongPass123!")
        request = RequestFactory().post("/accounts/login/")
        request.user = user
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        key = AuthRateLimitMiddleware._rate_limit_key(request, "auth-rate")

        self.assertEqual(key, f"auth-rate:/accounts/login/:127.0.0.1:user:{user.pk}")


class AnalyticsDashboardTests(TestCase):
    def setUp(self):
        bootstrap_roles_and_permissions()
        self.admin = set_role(User.objects.create_user("analytics-admin", password="StrongPass123!"), Role.ADMIN)
        self.engineer = set_role(User.objects.create_user("engineer", password="StrongPass123!"), Role.STAFF)
        self.category = Category.objects.create(name="Network Operations")
        record_type = RecordType.objects.create(name="Analytics Test")
        Record.objects.create(
            title="Switch repair",
            record_type=record_type,
            category=self.category,
            created_by=self.engineer,
            assigned_technician=self.engineer,
            maintenance_status="completed",
            priority="high",
            date_received=date.today() - timedelta(days=4),
            completion_date=date.today(),
        )

    def test_admin_analytics_dashboard_reports_record_signals(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin_analytics"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Network Operations")
        self.assertContains(response, "engineer")
        self.assertContains(response, "4.0")
        self.assertEqual(response.context["total_records"], 1)

    def test_non_admin_cannot_access_analytics_dashboard(self):
        self.client.force_login(self.engineer)

        response = self.client.get(reverse("admin_analytics"))

        self.assertEqual(response.status_code, 404)


class EmptyAnalyticsDashboardTests(TestCase):
    def setUp(self):
        bootstrap_roles_and_permissions()
        self.admin = set_role(User.objects.create_user("empty-analytics-admin", password="StrongPass123!"), Role.ADMIN)
        self.client.force_login(self.admin)

    def test_dashboard_renders_when_no_records_exist(self):
        response = self.client.get(reverse("admin_analytics"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_records"], 0)
        self.assertContains(response, "No category data yet.")
        self.assertContains(response, "No priority data yet.")
