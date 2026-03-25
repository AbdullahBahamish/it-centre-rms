import django.db.models.deletion
from django.db import migrations, models


ROLE_RANKS = {
    "ADMIN": 100,
    "MANAGER": 70,
    "STAFF": 40,
    "VIEWER": 10,
}


def apply_role_hierarchy(apps, schema_editor):
    Role = apps.get_model("accounts", "Role")
    UserProfile = apps.get_model("accounts", "UserProfile")

    viewer, _ = Role.objects.get_or_create(
        name="VIEWER",
        defaults={"description": "Read-only access.", "rank": ROLE_RANKS["VIEWER"]},
    )

    for role_name, rank in ROLE_RANKS.items():
        role, _ = Role.objects.get_or_create(
            name=role_name,
            defaults={"description": role_name.title(), "rank": rank},
        )
        role.rank = rank
        role.save(update_fields=["rank"])

    UserProfile.objects.filter(role__isnull=True).update(role=viewer)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_backfill_user_profiles"),
    ]

    operations = [
        migrations.AddField(
            model_name="role",
            name="rank",
            field=models.IntegerField(default=0),
        ),
        migrations.RunPython(apply_role_hierarchy, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="role",
            name="rank",
            field=models.IntegerField(unique=True),
        ),
        migrations.AlterField(
            model_name="userprofile",
            name="role",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="user_profiles",
                to="accounts.role",
            ),
        ),
    ]
