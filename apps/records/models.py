# apps/records/models.py

from django.db import models
from django.conf import settings
from .storage import record_attachment_path


class Record(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("archived", "Archived"),
    )

    title = models.CharField(max_length=255)
    record_type = models.CharField(max_length=100)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_records",
    )

    contributors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="contributed_records",
        blank=True,
    )

    case_description = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    retention_until = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_archived(self) -> bool:
        return self.status == "archived"

    def __str__(self) -> str:
        return f"{self.record_type}: {self.title}"
  

class RecordAttachment(models.Model):
    record = models.ForeignKey(
        Record,
        on_delete=models.CASCADE,
        related_name="attachments",
    )

    file = models.FileField(
        upload_to=record_attachment_path,
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name
