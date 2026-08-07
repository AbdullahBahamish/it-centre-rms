from rest_framework.permissions import BasePermission

from apps.core.services import AccessService


class RMSPermission(BasePermission):
    message = "You do not have permission to perform this action."

    ACTIONS = {
        "GET": "view_record",
        "HEAD": "view_record",
        "OPTIONS": "view_record",
        "POST": "create_record",
        "PUT": "update_record",
        "PATCH": "update_record",
        "DELETE": "delete_record",
    }

    def has_permission(self, request, view):
        action = getattr(view, "permission_action", None) or self.ACTIONS.get(request.method)
        if action == "view_record":
            action = "can_view_records"
        elif action == "create_record":
            action = "can_create_records"
        elif action == "update_record":
            action = "can_edit_records"
        elif action == "delete_record":
            action = "can_delete_records"
        return bool(action and AccessService.can(request.user, action))

    def has_object_permission(self, request, view, obj):
        action = getattr(view, "permission_action", None) or self.ACTIONS.get(request.method)
        if action in {"view_record", "update_record", "delete_record"}:
            return AccessService.can(request.user, action, obj)
        return self.has_permission(request, view)


class AdminPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and AccessService.can(request.user, "access_admin_panel"))


class AssetPermission(BasePermission):
    ACTIONS = {
        "GET": "can_view_records",
        "POST": "can_create_records",
        "PUT": "can_edit_records",
        "PATCH": "can_edit_records",
        "DELETE": "can_delete_records",
    }

    def has_permission(self, request, view):
        action = self.ACTIONS.get(request.method)
        return bool(action and AccessService.can(request.user, action))
