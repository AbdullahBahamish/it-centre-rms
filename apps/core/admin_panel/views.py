from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render

from apps.accounts.services import (
    RoleAssignmentService,
    RolePermissionService,
    activate_user as activate_user_service,
    deactivate_user as deactivate_user_service,
)
from apps.accounts.models import Role, RolePermission
from apps.core.permissions import admin_required
from apps.core.services import AccessService
from apps.core.security import log_security_failure

User = get_user_model()


class UserRoleAssignmentForm(forms.Form):
    role_id = forms.ModelChoiceField(queryset=Role.objects.all().order_by("-name"))


class RolePermissionForm(forms.ModelForm):
    class Meta:
        model = RolePermission
        fields = [
            "can_view_records",
            "can_create_records",
            "can_edit_records",
            "can_delete_records",
            "can_manage_users",
            "can_assign_roles",
        ]


def _require_permission(user, action, obj=None):
    if not AccessService.can(user, action, obj):
        raise Http404


@login_required
def admin_dashboard(request):
    if not AccessService.can(request.user, "access_admin_panel"):
        raise Http404
    return render(
        request,
        "admin_panel/dashboard.html",
        {
            "user_count": User.objects.count(),
            "active_user_count": User.objects.filter(is_active=True).count(),
            "role_count": Role.objects.count(),
        },
    )


@login_required
@admin_required
def user_management(request):
    actor_role = AccessService.get_role(request.user)
    users = (
        User.objects.select_related("userprofile__role")
        .annotate(record_count=Count("created_records"))
        .order_by("username")
    )
    return render(
        request,
        "admin_panel/user_management.html",
        {
            "users": users,
            "roles": Role.objects.filter(rank__lt=actor_role.rank).order_by("-rank", "name"),
            "can_manage_users": AccessService.can(request.user, "can_manage_users"),
            "can_assign_roles": AccessService.can(request.user, "can_assign_roles"),
        },
    )


@login_required
def assign_user_role(request, user_id):
    if request.method != "POST":
        return redirect("admin_user_management")

    form = UserRoleAssignmentForm(request.POST)
    if not form.is_valid():
        raise Http404

    role = form.cleaned_data["role_id"]
    result = RoleAssignmentService.assign(actor=request.user, target_id=user_id, new_role_id=role.id)
    if not result.success:
        raise Http404
    messages.success(request, "Role updated successfully.")
    return redirect("admin_user_management")


@login_required
def activate_user(request, user_id):
    if request.method != "POST":
        return redirect("admin_user_management")
    result = activate_user_service(actor=request.user, target=User.objects.filter(id=user_id).first())
    if not result.success:
        raise Http404
    messages.success(request, "User activated successfully.")
    return redirect("admin_user_management")


@login_required
def deactivate_user(request, user_id):
    if request.method != "POST":
        return redirect("admin_user_management")
    result = deactivate_user_service(actor=request.user, target=User.objects.filter(id=user_id).first())
    if not result.success:
        raise Http404
    messages.success(request, "User deactivated successfully.")
    return redirect("admin_user_management")


@login_required
def role_management(request):
    if not AccessService.can(request.user, "access_admin_panel"):
        raise Http404
    roles = Role.objects.select_related().order_by("-rank", "name")
    return render(request, "admin_panel/role_management.html", {"roles": roles})


@login_required
def permission_assignment(request):
    actor_role = AccessService.get_role(request.user)
    if actor_role.name != Role.ADMIN:
        raise Http404
    permissions = RolePermission.objects.select_related("role").filter(role__rank__lt=actor_role.rank).order_by("-role__rank", "role__name")
    return render(request, "admin_panel/permission_assignment.html", {"permissions": permissions})


@login_required
def update_role_permissions(request, role_id):
    if request.method != "POST":
        return redirect("admin_permission_assignment")

    role = Role.objects.filter(pk=role_id).first()
    if role is None:
        raise Http404
    _require_permission(request.user, "edit_role_permissions", role)
    permission_obj, _ = RolePermission.objects.get_or_create(role=role)
    form = RolePermissionForm(request.POST, instance=permission_obj)
    if not form.is_valid():
        raise Http404

    result = RolePermissionService.update(actor=request.user, role_id=role.id, form=form)
    if not result.success:
        raise Http404
    messages.success(request, "Permissions updated successfully.")
    return redirect("admin_permission_assignment")
