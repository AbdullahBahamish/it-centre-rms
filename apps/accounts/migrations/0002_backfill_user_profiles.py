from django.conf import settings
from django.db import migrations


def backfill_user_profiles(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    UserProfile = apps.get_model("accounts", "UserProfile")
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)

    default_role, _ = Role.objects.get_or_create(
        name="VIEWER",
        defaults={"description": "Read-only access."},
    )

    existing_profile_ids = set(UserProfile.objects.values_list("user_id", flat=True))
    missing_profiles = []
    for user in User.objects.all().only("id"):
        if user.id not in existing_profile_ids:
            missing_profiles.append(
                UserProfile(
                    user_id=user.id,
                    phone_number=f"user-{user.id}",
                    role=default_role,
                )
            )

    if missing_profiles:
        UserProfile.objects.bulk_create(missing_profiles)

    UserProfile.objects.filter(role__isnull=True).update(role=default_role)
    for profile in UserProfile.objects.filter(phone_number="").only("id", "user_id"):
        profile.phone_number = f"user-{profile.user_id}"
        profile.save(update_fields=["phone_number"])


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(backfill_user_profiles, migrations.RunPython.noop),
    ]
