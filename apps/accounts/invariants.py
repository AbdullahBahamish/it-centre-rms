import logging
import sys

from django.contrib.auth import get_user_model
from django.db import connections
from django.db.backends.signals import connection_created
from django.db.utils import OperationalError, ProgrammingError

from apps.accounts.models import Role, UserProfile

logger = logging.getLogger(__name__)

SKIP_COMMANDS = {"makemigrations", "migrate", "collectstatic", "shell", "dbshell"}
REQUIRED_TABLES = {"auth_user", "accounts_role", "accounts_rolepermission", "accounts_userprofile"}
VALIDATED_ALIASES = set()


def should_validate_runtime_invariants() -> bool:
    return not any(command in sys.argv for command in SKIP_COMMANDS)


def validate_runtime_invariants(*, using="default"):
    try:
        connection = connections[using]
        tables = set(connection.introspection.table_names())
    except (OperationalError, ProgrammingError):
        return

    if not REQUIRED_TABLES.issubset(tables):
        return

    User = get_user_model()
    missing_profile_id = User.objects.filter(userprofile__isnull=True).values_list("id", flat=True).first()
    if missing_profile_id is not None:
        logger.critical("Authority invariant failed: every user must have a profile.", extra={"using": using, "user_id": missing_profile_id})
        raise RuntimeError(f"Invariant violation: missing UserProfile for user_id={missing_profile_id}")

    missing_role_profile_id = UserProfile.objects.filter(role__isnull=True).values_list("user_id", flat=True).first()
    if missing_role_profile_id is not None:
        logger.critical("Authority invariant failed: every profile must have a role.", extra={"using": using, "user_id": missing_role_profile_id})
        raise RuntimeError(f"Invariant violation: missing role for user_id={missing_role_profile_id}")

    missing_permission_role_id = Role.objects.filter(permissions__isnull=True).values_list("id", flat=True).first()
    if missing_permission_role_id is not None:
        logger.critical("Authority invariant failed: every role must have permissions.", extra={"using": using, "role_id": missing_permission_role_id})
        raise RuntimeError(f"Invariant violation: missing permissions for role_id={missing_permission_role_id}")


def connect_runtime_invariant_guard():
    def _validate_on_connect(sender, connection, **kwargs):
        if connection.alias in VALIDATED_ALIASES or not should_validate_runtime_invariants():
            return
        validate_runtime_invariants(using=connection.alias)
        VALIDATED_ALIASES.add(connection.alias)

    connection_created.connect(_validate_on_connect, dispatch_uid="accounts.runtime_invariants")
