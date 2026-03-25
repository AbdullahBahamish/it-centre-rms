from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_role_hierarchy_and_profile_invariants"),
    ]

    operations = [
        migrations.CreateModel(
            name="Permission",
            fields=[],
            options={
                "verbose_name": "Permission",
                "verbose_name_plural": "Permissions",
                "proxy": True,
                "indexes": [],
                "constraints": [],
            },
            bases=("accounts.rolepermission",),
        ),
    ]
