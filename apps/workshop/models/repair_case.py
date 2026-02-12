from django.conf import settings
from django.db import models
from apps.core.models import BaseModel


class RepairCase(BaseModel):
    CATEGORY_CHOICES = [
        ("hardware", "Hardware Repair"),
        ("software", "Software Issue"),
        ("network", "Network"),
        ("maintenance", "Maintenance"),
        ("other", "Other"),
    ]

    technicians = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="repair_cases",
        help_text="Technicians who worked on this case"
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES
    )

    serial_number = models.CharField(max_length=100)
    device_type = models.CharField(max_length=100)
    brand_model = models.CharField(max_length=150)

    problem_description = models.TextField()
    actions_taken = models.TextField()

    final_status = models.CharField(
        max_length=20,
        choices=[("fixed", "Fixed"), ("not_fixed", "Not Fixed")]
    )

    source = models.CharField(
        max_length=20,
        default="public_form"
    )

    def __str__(self):
        return f"{self.serial_number} - {self.category}"
