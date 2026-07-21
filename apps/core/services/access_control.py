from dataclasses import dataclass

from django.db.models import Max

from apps.accounts.domain.constants import ADMIN, ADMIN_RANK, MANAGER_RANK
from apps.accounts.models import Role, UserProfile
from apps.core.security import log_security_failure


@dataclass(frozen=True)
class ResolvedRole:
    name: str
    rank: int = 0

    @property
    def permissions(self):
        return None


class AccessService:
    ANONYMOUS_ROLE_NAME = "anonymous"
    AUTHENTICATED_FALLBACK_ROLE_NAME = "user"
    GLOBAL_PERMISSION_FIELDS = {
        "can_view_records",
        "can_create_records",
        "can_edit_records",
        "can_delete_records",
        "can_manage_users",
        "can_assign_roles",
    }

    @classmethod
    def _fresh_user(cls, user):
        try:
            if not user or not getattr(user, "is_authenticated", False) or not getattr(user, "pk", None):
                return None

            return (
                user.__class__.objects.select_related("userprofile__role__permissions")
                .only(
                    "id",
                    "is_active",
                    "is_superuser",
                    "userprofile__id",
                    "userprofile__role__id",
                    "userprofile__role__name",
                    "userprofile__role__rank",
                    "userprofile__role__permissions__id",
                    "userprofile__role__permissions__can_view_records",
                    "userprofile__role__permissions__can_create_records",
                    "userprofile__role__permissions__can_edit_records",
                    "userprofile__role__permissions__can_delete_records",
                    "userprofile__role__permissions__can_manage_users",
                    "userprofile__role__permissions__can_assign_roles",
                )
                .get(pk=user.pk)
            )
        except Exception:
            log_security_failure(action="access_user_refresh", actor=user, reason="exception")
            return None

    @classmethod
    def _get_profile(cls, user):
        try:
            fresh_user = cls._fresh_user(user)
            return getattr(fresh_user, "userprofile", None) if fresh_user else None
        except Exception:
            log_security_failure(action="access_profile_lookup", actor=user, reason="exception")
            return None

    @classmethod
    def invalidate_user_cache(cls, user):
        return None

    @classmethod
    def invalidate_permission_cache_for_role(cls, role):
        return None

    @classmethod
    def _fallback_role(cls, user):
        if not user or not getattr(user, "is_authenticated", False):
            return ResolvedRole(name=cls.ANONYMOUS_ROLE_NAME)
        return ResolvedRole(name=cls.AUTHENTICATED_FALLBACK_ROLE_NAME)

    @classmethod
    def get_permissions(cls, user):
        try:
            role = cls.get_role(user)
            return getattr(role, "permissions", None)
        except Exception:
            log_security_failure(action="access_permissions_lookup", actor=user, reason="exception")
            return None

    @classmethod
    def get_role(cls, user):
        try:
            profile = cls._get_profile(user)
            if not profile or not profile.role_id:
                return cls._fallback_role(user)
            return profile.role
        except Exception:
            log_security_failure(action="access_role_lookup", actor=user, reason="exception")
            return cls._fallback_role(user)

    @classmethod
    def get_role_name(cls, user):
        return cls.get_role(user).name

    @classmethod
    def get_role_rank(cls, user):
        return getattr(cls.get_role(user), "rank", 0)

    @classmethod
    def _highest_role_rank(cls):
        try:
            return Role.objects.aggregate(max_rank=Max("rank")).get("max_rank") or ADMIN_RANK
        except Exception:
            log_security_failure(action="access_highest_role_rank", reason="exception")
            return ADMIN_RANK

    @classmethod
    def _is_highest_rank_role(cls, role):
        return bool(role and getattr(role, "rank", 0) == cls._highest_role_rank())

    @classmethod
    def has_global_permission(cls, user, action):
        try:
            permissions = cls.get_permissions(user)
            if not permissions:
                return False
            return bool(getattr(permissions, action, False))
        except Exception:
            log_security_failure(action="access_global_permission", actor=user, reason=action)
            return False

    @classmethod
    def can(cls, user, action, obj=None):
        try:
            if action in cls.GLOBAL_PERMISSION_FIELDS:
                return cls.has_global_permission(user, action)
            if action == "access_admin_panel":
                return cls.has_global_permission(user, "can_manage_users") or cls.has_global_permission(user, "can_assign_roles")
            if action == "access_category":
                return cls.can_access_category(user, obj)
            if action == "create_record":
                return cls.can_create_record(user, obj)
            if action == "view_record":
                return cls.can_view_record(user, obj)
            if action == "update_record":
                return cls.can_update_record(user, obj)
            if action == "delete_record":
                return cls.can_delete_record(user, obj)
            if action == "assign_role":
                if not isinstance(obj, dict):
                    return False
                return cls.can_assign_role(user, obj.get("target"), obj.get("new_role"))
            if action == "deactivate_user":
                return cls.can_deactivate_user(user, obj)
            if action == "edit_role_permissions":
                return cls.can_edit_role_permissions(user, obj)
            return False
        except Exception:
            log_security_failure(action="access_check", actor=user, reason=action)
            return False

    @classmethod
    def can_access_category(cls, user, category):
        try:
            if category is None:
                return False
            if not category.allowed_roles and not category.allowed_users.exists():
                return True
            if not user or not getattr(user, "is_authenticated", False):
                return False
            return (
                cls.get_role_name(user) in category.allowed_roles
                or category.allowed_users.filter(pk=user.pk).exists()
            )
        except Exception:
            log_security_failure(action="access_category", actor=user, target=getattr(category, "pk", None), reason="exception")
            return False

    @classmethod
    def can_create_record(cls, user, category):
        if not user or not getattr(user, "is_authenticated", False):
            return False
        return cls.has_global_permission(user, "can_create_records") and cls.can_access_category(user, category)

    @classmethod
    def can_view_record(cls, user, record):
        if record is None:
            return False
        if user and getattr(user, "is_authenticated", False):
            if not cls.has_global_permission(user, "can_view_records"):
                return False
            if cls.get_role_rank(user) >= ADMIN_RANK:
                return True
            if record.created_by_id == user.pk or record.contributors.filter(pk=user.pk).exists():
                return True
        return cls.can_access_category(user, record.category)

    @classmethod
    def can_update_record(cls, user, record):
        if record is None or not user or not getattr(user, "is_authenticated", False):
            return False
        if not cls.has_global_permission(user, "can_edit_records"):
            return False
        if cls.get_role_rank(user) >= ADMIN_RANK:
            return True
        if cls.get_role_rank(user) >= MANAGER_RANK:
            return cls.can_access_category(user, record.category)
        return record.created_by_id == user.pk or record.contributors.filter(pk=user.pk).exists()

    @classmethod
    def can_delete_record(cls, user, record):
        if record is None or not user or not getattr(user, "is_authenticated", False):
            return False
        if not cls.has_global_permission(user, "can_delete_records"):
            return False
        if cls.get_role_rank(user) >= ADMIN_RANK:
            return True
        if cls.get_role_rank(user) >= MANAGER_RANK:
            return cls.can_access_category(user, record.category)
        return record.created_by_id == user.pk

    @classmethod
    def can_assign_role(cls, actor, target, new_role):
        if (
            not actor
            or not getattr(actor, "is_authenticated", False)
            or target is None
            or new_role is None
            or actor.pk == target.pk
            or not cls.has_global_permission(actor, "can_assign_roles")
        ):
            return False

        actor_role = cls.get_role(actor)
        target_role = cls.get_role(target)
        return actor_role.outranks(target_role) and actor_role.outranks(new_role)

    @classmethod
    def can_deactivate_user(cls, actor, target):
        if (
            not actor
            or not getattr(actor, "is_authenticated", False)
            or target is None
            or actor.pk == target.pk
            or not cls.has_global_permission(actor, "can_manage_users")
        ):
            return False

        if not getattr(actor, "is_superuser", False) and cls.get_role_name(actor) != ADMIN:
            return False

        return cls.get_role(actor).outranks(cls.get_role(target))

    @classmethod
    def can_edit_role_permissions(cls, actor, role):
        actor_role = cls.get_role(actor)
        if not actor or not getattr(actor, "is_authenticated", False) or role is None:
            return False
        if actor_role.name != ADMIN or not cls._is_highest_rank_role(actor_role):
            return False
        return actor_role.outranks(role)
