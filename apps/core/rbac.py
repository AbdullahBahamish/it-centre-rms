from django.core.exceptions import ValidationError

from apps.accounts.domain.constants import LEGACY_ROLE_MAP, ROLE_NAMES
from apps.core.services import AccessService


ALLOWED_ROLES = set(ROLE_NAMES)


def normalize_role_code(value):
    if value in (None, ""):
        return None
    return LEGACY_ROLE_MAP.get(value, value)


def validate_role_codes(value):
    if value in (None, ""):
        return
    if not isinstance(value, list):
        raise ValidationError("Roles must be a list.")

    normalized = [normalize_role_code(role) for role in value]
    invalid = [role for role in normalized if role not in ALLOWED_ROLES]
    if invalid:
        raise ValidationError(f"Invalid roles: {', '.join(sorted(set(invalid)))}.")


def get_user_role(user):
    return AccessService.get_role_name(user)
