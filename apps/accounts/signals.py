from django.contrib.auth import get_user_model
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from apps.accounts.bootstrap import (
    bootstrap_initial_admin,
    bootstrap_existing_user_profiles,
    bootstrap_roles_and_permissions,
    ensure_user_profile,
)

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, raw, **kwargs):
    if raw or not created:
        return
    ensure_user_profile(user=instance)


@receiver(post_migrate)
def bootstrap_access_data(sender, app_config, using, **kwargs):
    if app_config is None or app_config.label != "accounts":
        return
    bootstrap_roles_and_permissions(using=using)
    bootstrap_existing_user_profiles(using=using)
    bootstrap_initial_admin(using=using)
