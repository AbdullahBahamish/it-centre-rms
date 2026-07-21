from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from apps.accounts.models import Role
from apps.core.services import AccessService
from apps.core.security import ServiceResult, log_security_event, log_security_failure, with_retry

User = get_user_model()


def activate_user(*, actor: Any, target: Any) -> ServiceResult:
    return UserLifecycleService.activate_user(actor=actor, target=target)


def deactivate_user(*, actor: Any, target: Any) -> ServiceResult:
    return UserLifecycleService.deactivate_user(actor=actor, target=target)


class UserLifecycleService:
    """Coordinates privileged user activation state changes under one authorization policy."""

    @staticmethod
    def activate(*, actor: Any, target_id: int) -> ServiceResult:
        result = with_retry(lambda: UserLifecycleService._set_active_once(actor=actor, target_id=target_id, is_active=True))
        if result.success:
            log_security_event(action="activate_user", actor=actor, target=target_id, result="allowed", reason=result.error or "updated")
        elif result.error == "deadlock":
            log_security_event(action="activate_user", actor=actor, target=target_id, result="denied", reason="deadlock")
        return result

    @staticmethod
    def activate_user(*, actor: Any, target: Any) -> ServiceResult:
        if target is None:
            return ServiceResult(success=False, error="not_found", status_code=404)
        return UserLifecycleService.activate(actor=actor, target_id=target.pk)

    @staticmethod
    def deactivate(*, actor: Any, target_id: int) -> ServiceResult:
        result = with_retry(lambda: UserLifecycleService._set_active_once(actor=actor, target_id=target_id, is_active=False))
        if result.success:
            log_security_event(action="deactivate_user", actor=actor, target=target_id, result="allowed", reason=result.error or "updated")
        elif result.error == "deadlock":
            log_security_event(action="deactivate_user", actor=actor, target=target_id, result="denied", reason="deadlock")
        return result

    @staticmethod
    def deactivate_user(*, actor: Any, target: Any) -> ServiceResult:
        if target is None:
            return ServiceResult(success=False, error="not_found", status_code=404)
        return UserLifecycleService.deactivate(actor=actor, target_id=target.pk)

    @staticmethod
    @transaction.atomic
    def _set_active_once(*, actor: Any, target_id: int, is_active: bool) -> ServiceResult:
        try:
            actor = User.objects.select_related("userprofile__role__permissions").select_for_update().get(pk=getattr(actor, "pk", None))
            target = User.objects.select_related("userprofile__role__permissions").select_for_update().get(pk=target_id)

            actor_role = AccessService.get_role(actor)
            is_admin_actor = bool(getattr(actor, "is_superuser", False)) or getattr(actor_role, "name", None) == Role.ADMIN
            if not is_admin_actor or actor.pk == target.pk or not AccessService.can(actor, "deactivate_user", target):
                return ServiceResult(success=False, error="not_found", status_code=404)

            if target.is_active == is_active:
                return ServiceResult(success=True, error="noop", payload=target)
            target.is_active = is_active
            target.save(update_fields=["is_active"])
            return ServiceResult(success=True, payload=target)
        except ObjectDoesNotExist:
            return ServiceResult(success=False, error="not_found", status_code=404)
        except Exception:
            action = "activate_user" if is_active else "deactivate_user"
            log_security_failure(action=action, actor=actor, target=target_id, reason="exception")
            return ServiceResult(success=False, error="permission_denied", status_code=404)


class UserManagementService:
    @staticmethod
    def activate(*, actor: Any, target_id: int) -> ServiceResult:
        return UserLifecycleService.activate(actor=actor, target_id=target_id)

    @staticmethod
    def activate_user(*, actor: Any, target: Any) -> ServiceResult:
        return UserLifecycleService.activate_user(actor=actor, target=target)

    @staticmethod
    def deactivate(*, actor: Any, target_id: int) -> ServiceResult:
        return UserLifecycleService.deactivate(actor=actor, target_id=target_id)

    @staticmethod
    def deactivate_user(*, actor: Any, target: Any) -> ServiceResult:
        return UserLifecycleService.deactivate_user(actor=actor, target=target)
