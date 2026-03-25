from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.rbac import validate_role_codes


SYSTEM_SETTINGS_CACHE_KEY = "access-policy:system-settings"


class SystemSettings(models.Model):
    require_login = models.BooleanField(default=True)
    allow_anonymous_view = models.BooleanField(default=False)
    allow_anonymous_create = models.BooleanField(default=False)
    allow_anonymous_update = models.BooleanField(default=False)
    allow_anonymous_delete = models.BooleanField(default=False)
    allowed_roles_for_repo_creation = models.JSONField(
        default=list,
        blank=True,
        validators=[validate_role_codes],
    )
    allowed_users_for_repo_creation = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="repo_creation_settings",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"

    def clean(self):
        super().clean()
        if self.pk is None and SystemSettings.objects.exists():
            raise ValidationError("Only one SystemSettings instance is allowed.")

    def save(self, *args, **kwargs):
        if not self.pk and SystemSettings.objects.exists():
            self.pk = SystemSettings.objects.values_list("pk", flat=True).first()
        super().save(*args, **kwargs)
        try:
            cache.delete(SYSTEM_SETTINGS_CACHE_KEY)
        except Exception:
            pass

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "System Settings"
