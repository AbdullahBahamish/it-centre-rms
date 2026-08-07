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


class RecordType(models.Model):
    name = models.CharField("Name", max_length=100, primary_key=True)
    created_at = models.DateTimeField("Created At", default=now_with_milliseconds, editable=False)
    updated_at = models.DateTimeField("Updated At", default=now_with_milliseconds)

    class Meta:
        verbose_name = "Record Type"
        verbose_name_plural = "Record Types"
        ordering = ("name",)

    def save(self, *args, **kwargs):
        if not self.created_at:
            self.created_at = now_with_milliseconds()
        self.updated_at = now_with_milliseconds()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


def get_default_record_type_name():
    record_type, _ = RecordType.objects.get_or_create(name="General")
    return record_type.name


class ITAsset(models.Model):
    DEVICE_TYPE_CHOICES = (
        ("desktop", "Desktop"),
        ("laptop", "Laptop"),
        ("server", "Server"),
        ("printer", "Printer"),
        ("monitor", "Monitor"),
        ("projector", "Projector"),
        ("scanner", "Scanner"),
        ("router", "Router"),
        ("switch", "Switch"),
        ("firewall", "Firewall"),
        ("access_point", "Access Point"),
        ("ups", "UPS"),
        ("nas", "NAS"),
        ("tablet", "Tablet"),
        ("phone", "Phone"),
        ("other", "Other"),
    )
    MANUFACTURER_CHOICES = (
        ("dell", "Dell"),
        ("hp", "HP"),
        ("lenovo", "Lenovo"),
        ("acer", "Acer"),
        ("asus", "ASUS"),
        ("cisco", "Cisco"),
        ("mikrotik", "Mikrotik"),
        ("apple", "Apple"),
        ("canon", "Canon"),
        ("epson", "Epson"),
        ("brother", "Brother"),
        ("other", "Other"),
    )
    OPERATING_SYSTEM_CHOICES = (
        ("windows_11", "Windows 11"),
        ("windows_10", "Windows 10"),
        ("windows_8_1", "Windows 8.1"),
        ("windows_7", "Windows 7"),
        ("ubuntu", "Ubuntu"),
        ("debian", "Debian"),
        ("fedora", "Fedora"),
        ("centos", "CentOS"),
        ("macos", "macOS"),
        ("android", "Android"),
        ("ios", "iOS"),
        ("none", "No Operating System"),
    )
    ARCHITECTURE_CHOICES = (
        ("x64", "x64"),
        ("x86", "x86"),
        ("arm64", "ARM64"),
    )
    STATUS_CHOICES = (
        ("active", "Active"),
        ("under_maintenance", "Under Maintenance"),
        ("retired", "Retired"),
        ("lost", "Lost"),
        ("disposed", "Disposed"),
        ("in_storage", "In Storage"),
    )

    asset_tag = models.CharField("Asset Tag", max_length=80, unique=True)
    barcode = models.CharField("Barcode / QR Code", max_length=120, blank=True)
    device_type = models.CharField("Device Type", max_length=30, choices=DEVICE_TYPE_CHOICES)
    manufacturer = models.CharField("Manufacturer", max_length=30, choices=MANUFACTURER_CHOICES, blank=True)
    model = models.CharField("Model", max_length=120, blank=True)
    serial_number = models.CharField("Serial Number", max_length=120, blank=True)
    operating_system = models.CharField("Operating System", max_length=30, choices=OPERATING_SYSTEM_CHOICES, blank=True)
    system_architecture = models.CharField("System Architecture", max_length=10, choices=ARCHITECTURE_CHOICES, blank=True)
    cpu = models.CharField("CPU", max_length=120, blank=True)
    ram = models.CharField("RAM", max_length=80, blank=True)
    storage = models.CharField("Storage", max_length=120, blank=True)
    location = models.CharField("Location", max_length=120, blank=True)
    department = models.CharField("Department", max_length=120, blank=True)
    room = models.CharField("Room", max_length=80, blank=True)
    assigned_user = models.CharField("Assigned User", max_length=150, blank=True)
    purchase_date = models.DateField("Purchase Date", null=True, blank=True)
    warranty_expiry = models.DateField("Warranty Expiry", null=True, blank=True)
    status = models.CharField("Status", max_length=30, choices=STATUS_CHOICES, default="active")
    notes = models.TextField("Notes", blank=True)
    created_at = models.DateTimeField("Created At", default=now_with_milliseconds, editable=False)
    updated_at = models.DateTimeField("Updated At", default=now_with_milliseconds)

    class Meta:
        verbose_name = "IT Asset"
        verbose_name_plural = "IT Assets"
        ordering = ("asset_tag",)

    def save(self, *args, **kwargs):
        self.asset_tag = (self.asset_tag or "").strip().upper()
        if not self.created_at:
            self.created_at = now_with_milliseconds()
        self.updated_at = now_with_milliseconds()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.asset_tag


class Record(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("archived", "Archived"),
    )
    MAINTENANCE_TYPE_CHOICES = (
        ("preventive", "Preventive"),
        ("corrective", "Corrective"),
        ("installation", "Installation"),
        ("upgrade", "Upgrade"),
        ("hardware_repair", "Hardware Repair"),
        ("software_repair", "Software Repair"),
        ("inspection", "Inspection"),
        ("network", "Network"),
    )
    PRIORITY_CHOICES = (
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    )
    MAINTENANCE_STATUS_CHOICES = (
        ("received", "Received"),
        ("diagnosing", "Diagnosing"),
        ("waiting_for_parts", "Waiting for Parts"),
        ("repairing", "Repairing"),
        ("testing", "Testing"),
        ("completed", "Completed"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    )
    FINAL_DEVICE_STATUS_CHOICES = (
        ("working", "Working"),
        ("working_with_limitations", "Working with Limitations"),
        ("beyond_repair", "Beyond Repair"),
        ("replaced", "Replaced"),
        ("returned_to_user", "Returned to User"),
        ("archived", "Archived"),
    )

    title = models.CharField("Title", max_length=255)
    record_type = models.ForeignKey(
        RecordType,
        on_delete=models.PROTECT,
        related_name="records",
        default=get_default_record_type_name,
        verbose_name="Record Type",
    )
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
    allow_all_contributors = models.BooleanField("Allow All Contributors", default=False)

    asset = models.ForeignKey(
        ITAsset,
        on_delete=models.PROTECT,
        related_name="maintenance_records",
        null=True,
        blank=True,
        verbose_name="IT Asset",
    )
    maintenance_type = models.CharField("Maintenance Type", max_length=30, choices=MAINTENANCE_TYPE_CHOICES, blank=True)
    problem_category = models.CharField("Problem Category", max_length=120, blank=True)
    priority = models.CharField("Priority", max_length=20, choices=PRIORITY_CHOICES, blank=True)
    reported_by = models.CharField("Reported By", max_length=150, blank=True)
    assigned_technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_maintenance_records",
        null=True,
        blank=True,
        verbose_name="Assigned Technician",
    )
    assistant_technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assisted_maintenance_records",
        null=True,
        blank=True,
        verbose_name="Assistant Technician",
    )
    support_team = models.CharField("Support Team", max_length=150, blank=True)
    date_received = models.DateField("Date Received", null=True, blank=True)
    expected_completion_date = models.DateField("Expected Completion Date", null=True, blank=True)
    maintenance_status = models.CharField("Maintenance Status", max_length=30, choices=MAINTENANCE_STATUS_CHOICES, blank=True)
    case_description = models.TextField("Problem Description", blank=True)
    diagnosis = models.TextField("Diagnosis", blank=True)
    repair_performed = models.TextField("Repair Performed", blank=True)
    software_installed = models.TextField("Software Installed", blank=True)
    drivers_installed = models.TextField("Driver Updates", blank=True)
    parts_replaced = models.TextField("Parts Replaced", blank=True)
    bios_updated = models.BooleanField("BIOS Updated", default=False)
    firmware_updated = models.BooleanField("Firmware Updates", default=False)
    testing_results = models.TextField("Testing Results", blank=True)
    remarks = models.TextField("Remarks", blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="completed_maintenance_records",
        null=True,
        blank=True,
        verbose_name="Completed By",
    )
    completion_date = models.DateField("Completion Date", null=True, blank=True)
    final_device_status = models.CharField("Final Outcome", max_length=40, choices=FINAL_DEVICE_STATUS_CHOICES, blank=True)

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
