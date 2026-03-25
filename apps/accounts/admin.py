from django.contrib import admin

from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "phone_number", "user__email")
