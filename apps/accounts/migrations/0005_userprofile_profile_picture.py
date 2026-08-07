from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_permission"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="profile_picture",
            field=models.FileField(
                blank=True,
                upload_to="profiles/",
                validators=[django.core.validators.validate_image_file_extension],
            ),
        ),
    ]
