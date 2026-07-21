from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import UserProfile


User = get_user_model()

admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    actions = ["activate_users", "deactivate_users"]

    def activate_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} user(s) activated.", messages.SUCCESS)

    activate_users.short_description = "Activate selected users"

    def deactivate_users(self, request, queryset):
        if request.user in queryset:
            self.message_user(request, "You cannot deactivate yourself.", messages.ERROR)
            return

        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} user(s) deactivated.", messages.WARNING)

    deactivate_users.short_description = "Deactivate selected users"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "phone_number", "user__email")
