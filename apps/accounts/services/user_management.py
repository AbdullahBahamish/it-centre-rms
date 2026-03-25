from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from apps.core.services import AccessService
from apps.core.security import ServiceResult, log_security_event, log_security_failure, with_retry

User = get_user_model()


class UserManagementService:
    @staticmethod
    def deactivate(*, actor, target_id):
        result = with_retry(lambda: UserManagementService._deactivate_once(actor=actor, target_id=target_id))
        if result.success:
            log_security_event(action="deactivate_user", actor=actor, target=target_id, result="allowed", reason=result.error or "updated")
        elif result.error == "deadlock":
            log_security_event(action="deactivate_user", actor=actor, target=target_id, result="denied", reason="deadlock")
        return result

    @staticmethod
    @transaction.atomic
    def _deactivate_once(*, actor, target_id):
        try:
            actor = User.objects.select_related("userprofile__role__permissions").select_for_update().get(pk=getattr(actor, "pk", None))
            target = User.objects.select_related("userprofile__role__permissions").select_for_update().get(pk=target_id)

            if not AccessService.can(actor, "deactivate_user", target):
                return ServiceResult(success=False, error="not_found", status_code=404)

            if not target.is_active:
                return ServiceResult(success=True, error="noop", payload=target)
            target.is_active = False
            target.save(update_fields=["is_active"])
            return ServiceResult(success=True, payload=target)
        except ObjectDoesNotExist:
            return ServiceResult(success=False, error="not_found", status_code=404)
        except Exception:
            log_security_failure(action="deactivate_user", actor=actor, target=target_id, reason="exception")
            return ServiceResult(success=False, error="permission_denied", status_code=404)
