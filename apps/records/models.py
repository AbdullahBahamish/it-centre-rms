# apps/records/models.py

from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from .storage import record_attachment_path


class Record(models.Model):
    STATUS_CHOICES = (
        ("active", _("Active")),
        ("archived", _("Archived")),
    )

    title = models.CharField(_("Title"), max_length=255)
    record_type = models.CharField(_("Record Type"), max_length=100)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_records",
        null=True,
        blank=True,
        verbose_name=_("Created By"),
    )

    contributors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="contributed_records",
        blank=True,
        verbose_name=_("Contributors"),
    )

    case_description = models.TextField(_("Case Description"), blank=True)

    status = models.CharField(
        _("Status"),
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    retention_until = models.DateField(_("Retention Until"), null=True, blank=True)

    created_at = models.DateTimeField(_("Created At"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Updated At"), auto_now=True)

    class Meta:
        verbose_name = _("Record")
        verbose_name_plural = _("Records")

    def is_archived(self) -> bool:
        return self.status == "archived"

    def __str__(self) -> str:
        return f"{self.record_type}: {self.title}"
  

class RecordAttachment(models.Model):
    record = models.ForeignKey(
        Record,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name=_("Record"),
    )

    file = models.FileField(
        _("File"),
        upload_to=record_attachment_path,
    )

    uploaded_at = models.DateTimeField(_("Uploaded At"), auto_now_add=True)

    class Meta:
        verbose_name = _("Record Attachment")
        verbose_name_plural = _("Record Attachments")

    def __str__(self):
        return self.file.name
