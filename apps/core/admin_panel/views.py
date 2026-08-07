from django import forms
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import Http404
from django.shortcuts import redirect, render
from django.conf import settings
from django.utils import timezone

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
from apps.records.models import Record
from datetime import date, timedelta
from pathlib import Path

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


def _distribution(queryset, field_name, labels):
    rows = list(queryset.values(field_name).annotate(total=Count("id")).order_by("-total", field_name))
    total = sum(row["total"] for row in rows) or 1
    return [
        {
            "key": row[field_name],
            "label": labels.get(row[field_name], row[field_name] or "Not specified"),
            "total": row["total"],
            "percent": round(row["total"] * 100 / total),
        }
        for row in rows
    ]


@login_required
def analytics_dashboard(request):
    if not AccessService.can(request.user, "access_admin_panel"):
        raise Http404

    records = Record.objects.select_related("category", "assigned_technician", "completed_by")
    today = timezone.localdate()
    completed_records = [
        record
        for record in records
        if record.date_received and record.completion_date and record.completion_date >= record.date_received
    ]
    turnaround_days = [
        (record.completion_date - record.date_received).days
        for record in completed_records
    ]
    open_records = records.filter(status="active")
    overdue_count = open_records.filter(expected_completion_date__lt=today).count()

    category_rows = list(records.values("category__name").annotate(total=Count("id")).order_by("-total", "category__name"))
    category_total = sum(row["total"] for row in category_rows) or 1
    categories = [
        {"label": row["category__name"], "total": row["total"], "percent": round(row["total"] * 100 / category_total)}
        for row in category_rows
    ]

    engineers = []
    engineer_rows = list(
        records.filter(assigned_technician__isnull=False)
        .values("assigned_technician__username")
        .annotate(total=Count("id"))
        .order_by("-total", "assigned_technician__username")[:8]
    )
    engineer_max = max((row["total"] for row in engineer_rows), default=1)
    for row in engineer_rows:
        name = row["assigned_technician__username"]
        assigned = [record for record in completed_records if record.assigned_technician and record.assigned_technician.username == name]
        engineer_turnaround = [
            (record.completion_date - record.date_received).days
            for record in assigned
        ]
        engineers.append(
            {
                "label": name,
                "total": row["total"],
                "percent": round(row["total"] * 100 / engineer_max),
                "average_days": round(sum(engineer_turnaround) / len(engineer_turnaround), 1) if engineer_turnaround else None,
            }
        )

    context = {
        "total_records": records.count(),
        "active_records": open_records.count(),
        "completed_records": records.filter(maintenance_status__in=("completed", "delivered")).count(),
        "overdue_count": overdue_count,
        "average_turnaround": round(sum(turnaround_days) / len(turnaround_days), 1) if turnaround_days else None,
        "categories": categories[:8],
        "engineers": engineers,
        "statuses": _distribution(records, "maintenance_status", dict(Record.MAINTENANCE_STATUS_CHOICES)),
        "priorities": _distribution(records, "priority", dict(Record.PRIORITY_CHOICES)),
        "today": today,
        "active_users": User.objects.filter(is_active=True).count(),
        "inactive_users": User.objects.filter(is_active=False).count(),
        "users_created_today": User.objects.filter(date_joined__date=today).count(),
        "users_created_week": User.objects.filter(date_joined__date__gte=today - timedelta(days=6)).count(),
        "users_created_month": User.objects.filter(date_joined__date__gte=today - timedelta(days=29)).count(),
        "user_roles": _distribution(User.objects.filter(userprofile__role__isnull=False), "userprofile__role__name", {role.name: role.display_name for role in Role.objects.all()}),
    }
    user_statuses = [
        {"label": "Active", "total": context["active_users"], "color": "#15803d"},
        {"label": "Inactive", "total": context["inactive_users"], "color": "#c2410c"},
    ]
    user_total = sum(item["total"] for item in user_statuses) or 1
    cursor = 0
    user_segments = []
    for item in user_statuses:
        percentage = round(item["total"] * 100 / user_total)
        item["percent"] = percentage
        user_segments.append(f"{item['color']} {cursor}% {cursor + percentage}%")
        cursor += percentage
    context["user_statuses"] = user_statuses
    context["user_status_pie_style"] = ", ".join(user_segments)

    month_points = []
    for offset in range(5, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=offset * 31)).replace(day=1)
        next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
        count = User.objects.filter(date_joined__date__gte=month_start, date_joined__date__lt=next_month).count()
        month_points.append({"label": month_start.strftime("%b"), "total": count})
    month_max = max((point["total"] for point in month_points), default=1) or 1
    for point in month_points:
        point["percent"] = round(point["total"] * 100 / month_max)
    context["user_creation_months"] = month_points

    log_path = Path(settings.LOG_DIR) / "security.log"
    log_lines = []
    log_warning = None
    try:
        if log_path.exists():
            log_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        log_warning = "Security log is temporarily unavailable."
    context["security_log_count"] = len(log_lines)
    context["recent_security_logs"] = log_lines[-8:][::-1]
    context["log_warning"] = log_warning
    priority_colors = ["#1a56a0", "#d97706", "#c2410c", "#64738c"]
    cursor = 0
    pie_segments = []
    for index, priority in enumerate(context["priorities"]):
        start = cursor
        cursor += priority["percent"]
        priority["color"] = priority_colors[index % len(priority_colors)]
        pie_segments.append(f"{priority['color']} {start}% {cursor}%")
    context["priority_pie_style"] = ", ".join(pie_segments) or "#e1e7f2 0 100%"
    return render(request, "admin_panel/analytics.html", context)


@login_required
@admin_required
def user_management(request):
    actor_role = AccessService.get_role(request.user)
    users = (
        User.objects.select_related("userprofile__role")
        .annotate(record_count=Count("created_records"))
        .order_by("username")
    )
    available_roles = list(Role.objects.filter(rank__lt=actor_role.rank).order_by("-rank", "name"))
    assignable_user_ids = {
        managed_user.id
        for managed_user in users
        if managed_user.id != request.user.id
        and any(
            AccessService.can(
                request.user,
                "assign_role",
                {"target": managed_user, "new_role": new_role},
            )
            for new_role in available_roles
        )
    }
    manageable_user_ids = {
        managed_user.id
        for managed_user in users
        if AccessService.can(request.user, "deactivate_user", managed_user)
    }
    return render(
        request,
        "admin_panel/user_management.html",
        {
            "users": users,
            "roles": available_roles,
            "can_manage_users": AccessService.can(request.user, "can_manage_users"),
            "can_assign_roles": AccessService.can(request.user, "can_assign_roles"),
            "assignable_user_ids": assignable_user_ids,
            "manageable_user_ids": manageable_user_ids,
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
