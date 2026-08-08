from django.urls import path

from . import views

urlpatterns = [
    path("", views.admin_dashboard, name="admin_dashboard"),
    path("analytics/", views.analytics_dashboard, name="admin_analytics"),
    path("password-reset-requests/", views.password_reset_requests, name="admin_password_reset_requests"),
    path("password-reset-requests/<int:request_id>/approve/", views.approve_password_reset_request, name="admin_approve_password_reset_request"),
    path("password-reset-requests/<int:request_id>/reject/", views.reject_password_reset_request, name="admin_reject_password_reset_request"),
    path("users/", views.user_management, name="admin_user_management"),
    path("users/<int:user_id>/activate/", views.activate_user, name="admin_activate_user"),
    path("users/<int:user_id>/assign-role/", views.assign_user_role, name="admin_assign_user_role"),
    path("users/<int:user_id>/deactivate/", views.deactivate_user, name="admin_deactivate_user"),
    path("roles/", views.role_management, name="admin_role_management"),
    path("permissions/", views.permission_assignment, name="admin_permission_assignment"),
    path("permissions/<int:role_id>/", views.update_role_permissions, name="admin_update_role_permissions"),
]
