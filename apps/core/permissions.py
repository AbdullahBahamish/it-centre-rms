from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from apps.core.services import AccessService
from apps.records.models import Category, Record


def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not AccessService.can(request.user, "access_admin_panel"):
            raise PermissionDenied("Admin access denied.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def record_permission_required(action):
    action_map = {
        "view": "view_record",
        "update": "update_record",
        "delete": "delete_record",
    }
    if action not in action_map:
        raise ValueError("Unsupported action for record_permission_required.")

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            record = get_object_or_404(Record, pk=kwargs.get("record_id"))
            if not AccessService.can(request.user, action_map[action], record):
                raise PermissionDenied("Access denied.")
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def record_create_permission_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.method == "POST":
            category = get_object_or_404(Category, pk=request.POST.get("category"))
            if not AccessService.can(request.user, "create_record", category):
                raise PermissionDenied("Create permission denied.")
        return view_func(request, *args, **kwargs)

    return _wrapped


def category_create_permission_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not getattr(request.user, "is_authenticated", False):
            raise PermissionDenied("Authentication is required to create categories.")
        return view_func(request, *args, **kwargs)

    return _wrapped
