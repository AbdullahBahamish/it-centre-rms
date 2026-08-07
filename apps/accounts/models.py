from django.conf import settings
from django.core.validators import validate_image_file_extension
from django.db import models

from apps.accounts.domain.constants import ADMIN, MANAGER, STAFF, VIEWER


class Role(models.Model):
    ADMIN = ADMIN
    MANAGER = MANAGER
    STAFF = STAFF
    VIEWER = VIEWER

    DISPLAY_NAMES = {
        ADMIN: "Administrator",
        MANAGER: "Manager",
        STAFF: "Staff",
        VIEWER: "Viewer",
    }

    name = models.CharField(max_length=50, unique=True)
    rank = models.IntegerField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        return self.DISPLAY_NAMES.get(self.name, self.name.replace("_", " ").title())

    def outranks(self, other) -> bool:
        if other is None:
            return True
        return self.rank > other.rank

    @property
    def permission(self):
        return getattr(self, "permissions", None)


class RolePermission(models.Model):
    role = models.OneToOneField(Role, on_delete=models.CASCADE, related_name="permissions")

    can_view_records = models.BooleanField(default=False)
    can_create_records = models.BooleanField(default=False)
    can_edit_records = models.BooleanField(default=False)
    can_delete_records = models.BooleanField(default=False)

    can_manage_users = models.BooleanField(default=False)
    can_assign_roles = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("role",), name="accounts_rolepermission_unique_role"),
        ]
        ordering = ("role__name",)

    def __str__(self):
        return f"{self.role.display_name} permissions"


class Permission(RolePermission):
    class Meta:
        proxy = True
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"


class UserProfile(models.Model):
    class Roles(models.TextChoices):
        ADMIN = ADMIN, "Admin"
        MANAGER = MANAGER, "Manager"
        STAFF = STAFF, "Staff"
        VIEWER = VIEWER, "Viewer"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="userprofile",
    )
    phone_number = models.CharField(max_length=30, unique=True)
    profile_picture = models.FileField(
        upload_to="profiles/",
        blank=True,
        validators=[validate_image_file_extension],
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="user_profiles",
    )

    class Meta:
        ordering = ("user__username",)

    def __str__(self) -> str:
        role_name = self.role.display_name if self.role else "Unassigned"
        return f"{self.user.username} ({self.phone_number}) - {role_name}"
