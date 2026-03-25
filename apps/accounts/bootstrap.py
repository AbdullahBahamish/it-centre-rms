import logging

from django.contrib.auth import get_user_model
from django.db import DEFAULT_DB_ALIAS, transaction

from apps.accounts.domain.constants import (
    ADMIN,
    DEFAULT_USER_ROLE,
    MANAGER,
    ROLE_RANKS,
    STAFF,
    VIEWER,
)
from apps.accounts.models import Role, RolePermission, UserProfile

logger = logging.getLogger(__name__)


ROLE_PERMISSION_MATRIX = {
    ADMIN: {
        "description": "Full system administration access.",
        "can_view_records": True,
        "can_create_records": True,
        "can_edit_records": True,
        "can_delete_records": True,
        "can_manage_users": True,
        "can_assign_roles": True,
    },
    MANAGER: {
        "description": "Operational management with limited user administration.",
        "can_view_records": True,
        "can_create_records": True,
        "can_edit_records": True,
        "can_delete_records": True,
        "can_manage_users": True,
        "can_assign_roles": False,
    },
    STAFF: {
        "description": "Record operators with CRUD access.",
        "can_view_records": True,
        "can_create_records": True,
        "can_edit_records": True,
        "can_delete_records": True,
        "can_manage_users": False,
        "can_assign_roles": False,
    },
    VIEWER: {
        "description": "Read-only access to records.",
        "can_view_records": True,
        "can_create_records": False,
        "can_edit_records": False,
        "can_delete_records": False,
        "can_manage_users": False,
        "can_assign_roles": False,
    },
}


def default_phone_number_for_user(user) -> str:
    return f"user-{user.pk}"


def bootstrap_roles_and_permissions(*, using=DEFAULT_DB_ALIAS):
    existing_roles = {
        role.name: role
        for role in Role.objects.using(using).all()
    }
    if existing_roles:
        logger.info("Authority bootstrap skipped because roles already exist.", extra={"using": using})
        return existing_roles

    role_lookup = {}
    with transaction.atomic(using=using):
        for name, config in ROLE_PERMISSION_MATRIX.items():
            role = Role.objects.using(using).create(
                name=name,
                description=config["description"],
                rank=ROLE_RANKS[name],
            )
            role_lookup[name] = role
            RolePermission.objects.using(using).create(
                role=role,
                can_view_records=config["can_view_records"],
                can_create_records=config["can_create_records"],
                can_edit_records=config["can_edit_records"],
                can_delete_records=config["can_delete_records"],
                can_manage_users=config["can_manage_users"],
                can_assign_roles=config["can_assign_roles"],
            )
    return role_lookup


def get_default_role(*, using=DEFAULT_DB_ALIAS):
    bootstrap_roles_and_permissions(using=using)
    role = Role.objects.using(using).filter(name=DEFAULT_USER_ROLE).first()
    if role is None:
        raise RuntimeError("Default role is missing.")
    return role


def ensure_user_profile(*, user, phone_number=None, using=DEFAULT_DB_ALIAS):
    if not user or not getattr(user, "pk", None):
        raise ValueError("A saved user instance is required to ensure a profile.")

    resolved_role = get_default_role(using=using)
    resolved_phone_number = (phone_number or "").strip() or default_phone_number_for_user(user)

    profile, _ = UserProfile.objects.using(using).get_or_create(
        user=user,
        defaults={
            "phone_number": resolved_phone_number,
            "role": resolved_role,
        },
    )

    updated_fields = []
    if phone_number and profile.phone_number != resolved_phone_number:
        profile.phone_number = resolved_phone_number
        updated_fields.append("phone_number")
    elif not profile.phone_number:
        profile.phone_number = resolved_phone_number
        updated_fields.append("phone_number")

    if profile.role_id is None and resolved_role is not None:
        profile.role = resolved_role
        updated_fields.append("role")

    if updated_fields:
        profile.save(update_fields=updated_fields)

    return profile


def bootstrap_existing_user_profiles(*, using=DEFAULT_DB_ALIAS):
    User = get_user_model()
    for user in User.objects.using(using).all().only("id"):
        ensure_user_profile(user=user, using=using)
