from unittest.mock import MagicMock, patch

from django.db import OperationalError

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.bootstrap import bootstrap_roles_and_permissions
from apps.accounts.models import Permission, Role, UserProfile
from apps.accounts.services import RoleAssignmentService
from apps.accounts.services.role_permissions import RolePermissionService
from apps.accounts.services.user_management import UserManagementService
from apps.accounts.invariants import validate_runtime_invariants
from apps.core.models import SystemSettings
from apps.core.services import AccessService

User = get_user_model()


def role(name):
    return Role.objects.get(name=name)


def force_role(user, role_name, phone_number):
    UserProfile.objects.filter(user=user).update(
        phone_number=phone_number,
        role=role(role_name),
    )
    AccessService.invalidate_user_cache(user)
    user.refresh_from_db()
    return user


class ProfileBootstrapTests(TestCase):
    def test_user_creation_bootstraps_profile_and_default_role(self):
        user = User.objects.create_user(username="bootstrap", email="bootstrap@example.com", password="StrongPass123!")

        profile = UserProfile.objects.select_related("role").get(user=user)

        self.assertEqual(profile.phone_number, f"user-{user.pk}")
        self.assertEqual(profile.role.name, Role.VIEWER)

    def test_role_bootstrap_populates_required_roles_with_ranks(self):
        Role.objects.all().delete()

        bootstrap_roles_and_permissions()

        expected = {
            Role.ADMIN: 100,
            Role.MANAGER: 70,
            Role.STAFF: 40,
            Role.VIEWER: 10,
        }
        self.assertEqual(dict(Role.objects.values_list("name", "rank")), expected)

    def test_role_exposes_single_permission_object_with_compatibility_api(self):
        admin_role = role(Role.ADMIN)

        self.assertTrue(hasattr(admin_role, "permission"))
        self.assertEqual(admin_role.permission.pk, admin_role.permissions.pk)
        self.assertIsInstance(Permission.objects.get(pk=admin_role.permission.pk), Permission)

    def test_bootstrap_does_not_reseed_existing_roles(self):
        admin_role = role(Role.ADMIN)
        original_rank = admin_role.rank
        admin_role.rank = 999
        admin_role.save(update_fields=["rank"])

        bootstrap_roles_and_permissions()

        admin_role.refresh_from_db()
        self.assertEqual(admin_role.rank, 999)
        self.assertNotEqual(admin_role.rank, original_rank)

    def test_runtime_invariant_guard_blocks_missing_profile(self):
        user = User.objects.create_user(username="repair", email="repair@example.com", password="StrongPass123!")
        UserProfile.objects.filter(user=user).delete()

        with self.assertRaises(RuntimeError):
            validate_runtime_invariants()


class SignupSecurityTests(TestCase):
    def test_signup_cannot_self_assign_privileged_role(self):
        response = self.client.post(
            reverse("signup"),
            {
                "username": "alice",
                "email": "alice@example.com",
                "phone_number": "1112223333",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
                "role": Role.ADMIN,
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(username="alice")
        self.assertEqual(user.userprofile.role.name, Role.VIEWER)


class PasswordRecoverySecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="OldPass123!",
        )
        force_role(self.user, Role.STAFF, "9998887777")

    def test_recovery_response_is_generic_for_unknown_identifier(self):
        response = self.client.post(
            reverse("recover_password"),
            {"identifier": "missing@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "If the account exists, password reset instructions have been sent.")

    def test_recovery_response_is_generic_for_known_identifier(self):
        response = self.client.post(
            reverse("recover_password"),
            {"identifier": "bob@example.com"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "If the account exists, password reset instructions have been sent.")

    @override_settings(AUTH_RATE_LIMITS={"/accounts/recover-password/": (1, 300)})
    def test_recovery_endpoint_is_rate_limited(self):
        self.client.post(reverse("recover_password"), {"identifier": "bob@example.com"})
        response = self.client.post(reverse("recover_password"), {"identifier": "bob@example.com"})
        self.assertEqual(response.status_code, 429)


class LoginRateLimitTests(TestCase):
    @override_settings(AUTH_RATE_LIMITS={"/accounts/login/": (1, 300)})
    def test_login_endpoint_is_rate_limited(self):
        User.objects.create_user(username="rate", email="rate@example.com", password="WrongPass123!")
        self.client.post(reverse("login"), {"username": "rate", "password": "bad-password"})
        response = self.client.post(reverse("login"), {"username": "rate", "password": "bad-password"})
        self.assertEqual(response.status_code, 429)

    @override_settings(AUTHORITY_MUTATION_RATE_LIMIT=(1, 300))
    def test_authority_mutation_endpoint_is_rate_limited(self):
        bootstrap_roles_and_permissions()
        admin = force_role(
            User.objects.create_user(username="adminrate", email="adminrate@example.com", password="StrongPass123!"),
            Role.ADMIN,
            "7555555501",
        )
        target = force_role(
            User.objects.create_user(username="targetrate", email="targetrate@example.com", password="StrongPass123!"),
            Role.VIEWER,
            "7555555502",
        )
        self.client.force_login(admin)

        self.client.post(reverse("admin_assign_user_role", args=[target.id]), {"role_id": role(Role.STAFF).id})
        response = self.client.post(reverse("admin_assign_user_role", args=[target.id]), {"role_id": role(Role.STAFF).id})

        self.assertEqual(response.status_code, 429)


class AccessMiddlewareResilienceTests(TestCase):
    def setUp(self):
        self.system_settings = SystemSettings.get_solo()

    def test_password_reset_endpoints_remain_public(self):
        self.system_settings.require_login = True
        self.system_settings.allow_anonymous_view = False
        self.system_settings.save()

        response = self.client.get(reverse("password_reset"))
        self.assertEqual(response.status_code, 200)

    def test_middleware_denies_when_system_settings_lookup_fails(self):
        with patch("apps.core.middleware.SystemSettings.get_solo", side_effect=RuntimeError("db down")):
            response = self.client.get(reverse("record_list"))

        self.assertEqual(response.status_code, 403)

    def test_access_service_denies_when_profile_lookup_fails(self):
        user = User.objects.create_user(username="fail", email="fail@example.com", password="StrongPass123!")
        with patch.object(User.objects, "select_related", side_effect=RuntimeError("db down")):
            self.assertFalse(AccessService.can(user, "can_view_records"))


class AdminAuthorityTests(TestCase):
    def setUp(self):
        bootstrap_roles_and_permissions()
        self.admin = force_role(
            User.objects.create_user(username="admin", email="admin@example.com", password="StrongPass123!"),
            Role.ADMIN,
            "7000000001",
        )
        self.manager = force_role(
            User.objects.create_user(username="manager", email="manager@example.com", password="StrongPass123!"),
            Role.MANAGER,
            "7000000002",
        )
        self.target = force_role(
            User.objects.create_user(username="target", email="target@example.com", password="StrongPass123!"),
            Role.VIEWER,
            "7000000003",
        )

    def test_self_role_assignment_fails(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("admin_assign_user_role", args=[self.admin.id]),
            {"role_id": role(Role.ADMIN).id},
        )

        self.assertEqual(response.status_code, 404)

    def test_equal_or_higher_role_assignment_fails(self):
        self.client.force_login(self.manager)
        manager_role = role(Role.MANAGER)
        manager_role.permissions.can_assign_roles = True
        manager_role.permissions.save(update_fields=["can_assign_roles"])

        response = self.client.post(
            reverse("admin_assign_user_role", args=[self.target.id]),
            {"role_id": role(Role.MANAGER).id},
        )

        self.assertEqual(response.status_code, 404)

    def test_non_admin_cannot_edit_role_permissions(self):
        manager_role = role(Role.MANAGER)
        manager_role.permissions.can_assign_roles = True
        manager_role.permissions.save(update_fields=["can_assign_roles"])
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse("admin_update_role_permissions", args=[role(Role.VIEWER).id]),
            {"can_view_records": "on", "can_manage_users": "on", "can_assign_roles": "on"},
        )

        self.assertEqual(response.status_code, 404)

    def test_admin_cannot_edit_own_role_permissions(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("admin_update_role_permissions", args=[role(Role.ADMIN).id]),
            {"can_view_records": "on", "can_manage_users": "on", "can_assign_roles": "on"},
        )

        self.assertEqual(response.status_code, 404)

    def test_deactivation_of_higher_or_equal_rank_fails(self):
        self.client.force_login(self.manager)

        response = self.client.post(reverse("admin_deactivate_user", args=[self.admin.id]))

        self.assertEqual(response.status_code, 404)

    def test_role_assignment_returns_safe_denial_on_exception(self):
        with patch("apps.accounts.services.role_assignment.Role.objects.only", side_effect=RuntimeError("db error")):
            result = RoleAssignmentService.assign(
                actor=self.admin,
                target_id=self.target.id,
                new_role_id=role(Role.VIEWER).id,
            )

        self.assertFalse(result.success)
        self.assertEqual(result.status_code, 404)

    def test_service_repairs_missing_target_profile_before_assignment(self):
        self.client.force_login(self.admin)
        UserProfile.objects.filter(user=self.target).delete()

        response = self.client.post(
            reverse("admin_assign_user_role", args=[self.target.id]),
            {"role_id": role(Role.STAFF).id},
        )

        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertEqual(self.target.userprofile.role.name, Role.STAFF)

    def test_role_assignment_locks_target_row(self):
        actor_select = MagicMock()
        actor_locked = MagicMock()
        actor_locked.get.return_value = self.admin
        actor_select.select_for_update.return_value = actor_locked

        target_select = MagicMock()
        target_locked = MagicMock()
        target_locked.get.return_value = self.target
        target_select.select_for_update.return_value = target_locked

        role_only = MagicMock()
        role_locked = MagicMock()
        role_locked.get.return_value = role(Role.STAFF)
        role_only.select_for_update.return_value = role_locked

        with patch("apps.accounts.services.role_assignment.User.objects.select_related", side_effect=[actor_select, target_select]), patch(
            "apps.accounts.services.role_assignment.Role.objects.only",
            return_value=role_only,
        ), patch(
            "apps.accounts.services.role_assignment.AccessService.can",
            return_value=True,
        ), patch(
            "apps.accounts.services.role_assignment.UserProfileRepository.ensure_profile",
            return_value=self.target.userprofile,
        ):
            result = RoleAssignmentService.assign(
                actor=self.admin,
                target_id=self.target.id,
                new_role_id=role(Role.STAFF).id,
            )

        self.assertTrue(result.success)
        target_select.select_for_update.assert_called_once()
        actor_select.select_for_update.assert_called_once()
        role_only.select_for_update.assert_called_once()

    def test_role_assignment_retries_deadlock(self):
        with patch(
            "apps.accounts.services.role_assignment.RoleAssignmentService._assign_once",
            side_effect=[OperationalError("deadlock"), MagicMock(success=True, error=None, payload=self.target.userprofile)],
        ) as mocked:
            result = RoleAssignmentService.assign(
                actor=self.admin,
                target_id=self.target.id,
                new_role_id=role(Role.STAFF).id,
            )

        self.assertTrue(result.success)
        self.assertEqual(mocked.call_count, 2)

    def test_role_assignment_same_role_is_noop(self):
        result = RoleAssignmentService.assign(
            actor=self.admin,
            target_id=self.target.id,
            new_role_id=role(Role.VIEWER).id,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.error, "noop")

    def test_deactivate_inactive_user_is_noop(self):
        self.target.is_active = False
        self.target.save(update_fields=["is_active"])

        result = UserManagementService.deactivate(actor=self.admin, target_id=self.target.id)

        self.assertTrue(result.success)
        self.assertEqual(result.error, "noop")

    def test_permission_update_retries_deadlock(self):
        form = MagicMock()
        role_id = role(Role.VIEWER).id
        expected = MagicMock(success=True, error=None, payload=role(Role.VIEWER).permissions)
        with patch(
            "apps.accounts.services.role_permissions.RolePermissionService._update_once",
            side_effect=[OperationalError("deadlock"), expected],
        ) as mocked:
            result = RolePermissionService.update(actor=self.admin, role_id=role_id, form=form)

        self.assertTrue(result.success)
        self.assertEqual(mocked.call_count, 2)
