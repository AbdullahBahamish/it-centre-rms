from django.contrib import admin

from .models import SystemSettings


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "require_login",
        "allow_anonymous_view",
        "allow_anonymous_create",
        "allow_anonymous_update",
        "allow_anonymous_delete",
        "updated_at",
    )
    def has_add_permission(self, request):
        if SystemSettings.objects.exists():
            return False
        return super().has_add_permission(request)
