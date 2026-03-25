from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from apps.accounts.models import RolePermission
from apps.core.services import AccessService
from apps.core.security import ServiceResult, log_security_event, log_security_failure, with_retry

User = get_user_model()


class RolePermissionService:
    EDITABLE_FIELDS = (
        "can_view_records",
        "can_create_records",
        "can_edit_records",
        "can_delete_records",
        "can_manage_users",
        "can_assign_roles",
    )

    @classmethod
    def update(cls, *, actor, role_id, form):
        result = with_retry(lambda: cls._update_once(actor=actor, role_id=role_id, form=form))
        if result.success:
            log_security_event(action="update_role_permissions", actor=actor, target=role_id, result="allowed", reason=result.error or "updated")
        elif result.error == "deadlock":
            log_security_event(action="update_role_permissions", actor=actor, target=role_id, result="denied", reason="deadlock")
        return result

    @classmethod
    @transaction.atomic
    def _update_once(cls, *, actor, role_id, form):
        try:
            actor = User.objects.select_related("userprofile__role__permissions").select_for_update().get(pk=getattr(actor, "pk", None))
            permission_obj = RolePermission.objects.select_related("role").select_for_update().get(role_id=role_id)

            role = permission_obj.role
            if not AccessService.can(actor, "edit_role_permissions", role):
                return ServiceResult(success=False, error="not_found", status_code=404)

            pending = form.save(commit=False)
            changed = False
            for field in cls.EDITABLE_FIELDS:
                value = getattr(pending, field)
                if getattr(permission_obj, field) != value:
                    setattr(permission_obj, field, value)
                    changed = True
            if not changed:
                return ServiceResult(success=True, error="noop", payload=permission_obj)
            permission_obj.save(update_fields=list(cls.EDITABLE_FIELDS))
            return ServiceResult(success=True, payload=permission_obj)
        except ObjectDoesNotExist:
            return ServiceResult(success=False, error="not_found", status_code=404)
        except Exception:
            log_security_failure(action="update_role_permissions", actor=actor, target=role_id, reason="exception")
            return ServiceResult(success=False, error="permission_denied", status_code=404)
