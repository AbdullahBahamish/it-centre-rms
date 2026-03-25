from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.rbac import validate_role_codes
from .storage import record_attachment_path


def now_with_milliseconds():
    current = timezone.now()
    return current.replace(microsecond=(current.microsecond // 1000) * 1000)


class Category(models.Model):
    name = models.CharField("Name", max_length=100, unique=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_categories",
        verbose_name="Created By",
    )
    allowed_roles = models.JSONField(
        "Allowed Roles",
        default=list,
        blank=True,
        validators=[validate_role_codes],
        help_text="Empty means no role restriction.",
    )
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="allowed_categories",
        verbose_name="Allowed Users",
    )
    created_at = models.DateTimeField("Created At", default=now_with_milliseconds, editable=False)
    updated_at = models.DateTimeField("Updated At", default=now_with_milliseconds)

    class Meta:
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        ordering = ("name",)

    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = now_with_milliseconds()
        self.updated_at = now_with_milliseconds()
        super().save(*args, **kwargs)

    @property
    def has_restrictions(self) -> bool:
        return bool(self.allowed_roles) or self.allowed_users.exists()

    def __str__(self) -> str:
        return self.name


def get_default_category_id():
    category, _ = Category.objects.get_or_create(name="Maintenance")
    return category.id


class Record(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("archived", "Archived"),
    )

    title = models.CharField("Title", max_length=255)
    record_type = models.CharField("Record Type", max_length=100)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="records",
        default=get_default_category_id,
        verbose_name="Category",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_records",
        null=True,
        blank=True,
        verbose_name="Created By",
    )

    contributors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="contributed_records",
        blank=True,
        verbose_name="Contributors",
    )

    case_description = models.TextField("Case Description", blank=True)

    status = models.CharField(
        "Status",
        max_length=20,
        choices=STATUS_CHOICES,
        default="active",
    )

    retention_until = models.DateField("Retention Until", null=True, blank=True)
    pdf_file = models.FileField("PDF File", upload_to="backup/records/pdfs", blank=True)
    created_at = models.DateTimeField("Created At", default=now_with_milliseconds, editable=False)
    updated_at = models.DateTimeField("Updated At", default=now_with_milliseconds)

    class Meta:
        verbose_name = "Record"
        verbose_name_plural = "Records"

    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = now_with_milliseconds()
        self.updated_at = now_with_milliseconds()
        super().save(*args, **kwargs)

    def is_archived(self) -> bool:
        return self.status == "archived"

    def __str__(self) -> str:
        return f"{self.record_type}: {self.title}"


class RecordAttachment(models.Model):
    record = models.ForeignKey(
        Record,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="Record",
    )

    file = models.FileField(
        "File",
        upload_to=record_attachment_path,
    )

    uploaded_at = models.DateTimeField("Uploaded At", auto_now_add=True)

    class Meta:
        verbose_name = "Record Attachment"
        verbose_name_plural = "Record Attachments"

    @property
    def display_name(self) -> str:
        return Path(self.file.name).name

    def __str__(self):
        return self.display_name
