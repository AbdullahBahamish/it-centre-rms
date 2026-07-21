import apps.records.models
from django.db import migrations, models
import django.db.models.deletion


def seed_record_types(apps, schema_editor):
    Record = apps.get_model("records", "Record")
    RecordType = apps.get_model("records", "RecordType")

    existing_names = {
        value.strip()
        for value in Record.objects.exclude(record_type="").values_list("record_type", flat=True)
        if value and value.strip()
    }
    existing_names.add("General")

    for name in sorted(existing_names):
        RecordType.objects.get_or_create(name=name)


class Migration(migrations.Migration):

    dependencies = [
        ("records", "0005_record_pdf_file_alter_record_created_at_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="RecordType",
            fields=[
                ("name", models.CharField(max_length=100, primary_key=True, serialize=False, verbose_name="Name")),
                ("created_at", models.DateTimeField(default=apps.records.models.now_with_milliseconds, editable=False, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(default=apps.records.models.now_with_milliseconds, verbose_name="Updated At")),
            ],
            options={
                "verbose_name": "Record Type",
                "verbose_name_plural": "Record Types",
                "ordering": ("name",),
            },
        ),
        migrations.RunPython(seed_record_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="record",
            name="record_type",
            field=models.ForeignKey(
                default=apps.records.models.get_default_record_type_name,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="records",
                to="records.recordtype",
                verbose_name="Record Type",
            ),
        ),
        migrations.AddField(
            model_name="record",
            name="allow_all_contributors",
            field=models.BooleanField(default=False, verbose_name="Allow All Contributors"),
        ),
    ]
