from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="systemsettings",
            name="allowed_roles_for_repo_creation",
        ),
        migrations.RemoveField(
            model_name="systemsettings",
            name="allowed_users_for_repo_creation",
        ),
    ]
