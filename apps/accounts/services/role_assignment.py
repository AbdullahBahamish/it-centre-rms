from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.accounts.infrastructure.repositories import UserProfileRepository
from apps.accounts.models import Role
from apps.core.services import AccessService
from apps.core.security import ServiceResult, log_security_event, log_security_failure, with_retry

User = get_user_model()


class RoleAssignmentService:
    @staticmethod
    def assign(*, actor, target_id, new_role_id):
        result = with_retry(lambda: RoleAssignmentService._assign_once(actor=actor, target_id=target_id, new_role_id=new_role_id))
        if result.success:
            log_security_event(
                action="assign_role",
                actor=actor,
                target=target_id,
                result="allowed",
                reason=result.error or "updated",
                new_role=getattr(getattr(result.payload, "role", None), "name", None),
            )
        elif result.error == "deadlock":
            log_security_event(action="assign_role", actor=actor, target=target_id, result="denied", reason="deadlock")
        return result

    @staticmethod
    @transaction.atomic
    def _assign_once(*, actor, target_id, new_role_id):
        try:
            actor = User.objects.select_related("userprofile__role__permissions").select_for_update().get(pk=getattr(actor, "pk", None))
            target = User.objects.select_related("userprofile__role__permissions").select_for_update().get(pk=target_id)
            new_role = Role.objects.only("id", "name", "rank").select_for_update().get(pk=new_role_id)

            if not AccessService.can(actor, "assign_role", {"target": target, "new_role": new_role}):
                return ServiceResult(success=False, error="not_found", status_code=404)

            profile = UserProfileRepository().ensure_profile(user=target)
            if profile.role_id == new_role.id:
                return ServiceResult(success=True, error="noop", payload=profile)
            profile.role = new_role
            profile.save(update_fields=["role"])
            return ServiceResult(success=True, payload=profile)
        except ObjectDoesNotExist:
            return ServiceResult(success=False, error="not_found", status_code=404)
        except Exception:
            log_security_failure(action="assign_role", actor=actor, target=target_id, reason="exception")
            return ServiceResult(success=False, error="permission_denied", status_code=404)
