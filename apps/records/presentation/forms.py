import json

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.accounts.models import Role
from apps.records.models import Category, ITAsset, Record, RecordType

User = get_user_model()


PRIVILEGED_ROLES = (Role.ADMIN, Role.MANAGER)


def contributor_queryset(*, category=None, allow_all=False):
    queryset = User.objects.select_related("userprofile__role").filter(is_active=True).order_by("username")
    if allow_all or category is None:
        return queryset

    privileged_filter = Q(userprofile__role__name__in=PRIVILEGED_ROLES)
    unrestricted = not category.allowed_roles and not category.allowed_users.exists()
    if unrestricted:
        return queryset

    category_filter = Q(userprofile__role__name__in=category.allowed_roles) | Q(id__in=category.allowed_users.values_list("id", flat=True))
    return queryset.filter(privileged_filter | category_filter).distinct()


class RecordForm(forms.Form):
    title = forms.CharField(max_length=255, label="Title")
    record_type = forms.ModelChoiceField(queryset=RecordType.objects.none(), label="Record Type")
    category = forms.ModelChoiceField(queryset=Category.objects.none(), label="Category")
    retention_until = forms.DateField(
        required=False,
        label="Retention Until",
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )
    asset_tag = forms.CharField(max_length=80, required=False, label="Asset Tag")
    device_type = forms.ChoiceField(choices=(("", "Select device type"),) + ITAsset.DEVICE_TYPE_CHOICES, required=False, label="Device Type")
    manufacturer = forms.ChoiceField(choices=(("", "Select manufacturer"),) + ITAsset.MANUFACTURER_CHOICES, required=False, label="Manufacturer")
    model = forms.CharField(max_length=120, required=False, label="Model")
    serial_number = forms.CharField(max_length=120, required=False, label="Serial Number")
    operating_system = forms.ChoiceField(choices=(("", "Select operating system"),) + ITAsset.OPERATING_SYSTEM_CHOICES, required=False, label="Operating System")
    system_architecture = forms.ChoiceField(choices=(("", "Select architecture"),) + ITAsset.ARCHITECTURE_CHOICES, required=False, label="System Architecture")
    cpu = forms.CharField(max_length=120, required=False, label="CPU")
    ram = forms.CharField(max_length=80, required=False, label="RAM")
    storage = forms.CharField(max_length=120, required=False, label="Storage")
    location = forms.CharField(max_length=120, required=False, label="Location")
    department = forms.CharField(max_length=120, required=False, label="Department")
    room = forms.CharField(max_length=80, required=False, label="Room")
    device_owner = forms.CharField(max_length=150, required=False, label="Device Owner")
    maintenance_type = forms.ChoiceField(choices=(("", "Select maintenance type"),) + Record.MAINTENANCE_TYPE_CHOICES, required=False, label="Maintenance Type")
    problem_category = forms.CharField(max_length=120, required=False, label="Problem Category")
    priority = forms.ChoiceField(choices=(("", "Select priority"),) + Record.PRIORITY_CHOICES, required=False, label="Priority")
    reported_by = forms.CharField(max_length=150, required=False, label="Reported By")
    assigned_technician = forms.ModelChoiceField(queryset=User.objects.none(), required=False, label="Assigned Technician")
    assistant_technician = forms.ModelChoiceField(queryset=User.objects.none(), required=False, label="Assistant Technician")
    support_team = forms.CharField(max_length=150, required=False, label="Support Team")
    date_received = forms.DateField(required=False, label="Date Received", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    expected_completion_date = forms.DateField(required=False, label="Expected Completion Date", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    maintenance_status = forms.ChoiceField(choices=(("", "Select status"),) + Record.MAINTENANCE_STATUS_CHOICES, required=False, label="Status")
    allow_all_contributors = forms.BooleanField(required=False, label="Allow All Contributors")
    contributors = forms.CharField(required=False, label="Contributors", widget=forms.HiddenInput())
    case_description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        label="Problem Description",
    )
    diagnosis = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Diagnosis")
    repair_performed = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Repair Performed")
    software_installed = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Software Installed")
    drivers_installed = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Drivers Installed")
    parts_replaced = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Parts Replaced")
    bios_updated = forms.BooleanField(required=False, label="BIOS Updated")
    firmware_updated = forms.BooleanField(required=False, label="Firmware Updated")
    testing_results = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Testing Results")
    remarks = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), required=False, label="Remarks")
    completed_by = forms.ModelChoiceField(queryset=User.objects.none(), required=False, label="Completed By")
    completion_date = forms.DateField(required=False, label="Completion Date", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    final_device_status = forms.ChoiceField(choices=(("", "Select final status"),) + Record.FINAL_DEVICE_STATUS_CHOICES, required=False, label="Final Device Status")

    def __init__(self, *args, categories=None, record_types=None, record=None, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(categories, list):
            categories = Category.objects.filter(id__in=[category.id for category in categories])
        if isinstance(record_types, list):
            record_types = RecordType.objects.filter(name__in=[record_type.name for record_type in record_types])

        categories = categories if categories is not None else Category.objects.none()
        record_types = record_types if record_types is not None else RecordType.objects.none()
        self.fields["category"].queryset = categories
        self.fields["record_type"].queryset = record_types

        selected_category = self._selected_category(categories=categories, record=record)
        allow_all = self._allow_all_contributors(record=record)
        allowed_contributors = contributor_queryset(category=selected_category, allow_all=allow_all)
        self.allowed_contributors = list(allowed_contributors)
        self.allowed_contributor_ids = {user.id for user in self.allowed_contributors}
        self.all_contributors = list(contributor_queryset(category=selected_category, allow_all=True))
        technician_queryset = User.objects.select_related("userprofile__role").filter(is_active=True).order_by("username")
        self.fields["assigned_technician"].queryset = technician_queryset
        self.fields["assistant_technician"].queryset = technician_queryset
        self.fields["completed_by"].queryset = technician_queryset
        self.contributor_options = self._contributor_options(categories=categories)
        if not self.is_bound:
            selected_ids = self._initial_contributor_ids(record=record)
            self.initial["contributors"] = json.dumps(selected_ids)

    def _selected_category(self, *, categories, record=None):
        if self.is_bound:
            raw_value = self.data.get(self.add_prefix("category"))
            if raw_value:
                return categories.filter(pk=raw_value).first()
        initial_value = self.initial.get("category")
        if initial_value:
            category_id = getattr(initial_value, "pk", initial_value)
            return categories.filter(pk=category_id).first()
        if record is not None:
            return categories.filter(pk=record.category_id).first()
        return categories.first()

    def _allow_all_contributors(self, *, record=None):
        if self.is_bound:
            return self.data.get(self.add_prefix("allow_all_contributors")) in {"on", "true", "1"}
        initial_value = self.initial.get("allow_all_contributors")
        if initial_value is not None:
            return bool(initial_value)
        if record is not None:
            return bool(record.allow_all_contributors)
        return False

    def _initial_contributor_ids(self, *, record=None):
        initial_value = self.initial.get("contributors")
        if initial_value is not None:
            if hasattr(initial_value, "values_list"):
                return list(initial_value.values_list("id", flat=True))
            if isinstance(initial_value, (list, tuple)):
                return [getattr(value, "id", value) for value in initial_value]
        if record is not None:
            return list(record.contributors.values_list("id", flat=True))
        return []

    def _contributor_options(self, *, categories):
        def serialize(users):
            return [{"id": user.id, "username": user.username} for user in users]

        return {
            "all": serialize(self.all_contributors),
            "byCategory": {
                str(category.id): serialize(contributor_queryset(category=category))
                for category in categories
            },
        }

    def clean_contributors(self):
        raw_value = self.cleaned_data.get("contributors") or "[]"
        try:
            contributor_ids = json.loads(raw_value)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError("Invalid contributors selection.") from exc

        if not isinstance(contributor_ids, list):
            raise forms.ValidationError("Invalid contributors selection.")

        normalized_ids = []
        seen_ids = set()
        for value in contributor_ids:
            try:
                user_id = int(value)
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError("Invalid contributors selection.") from exc
            if user_id in seen_ids:
                continue
            seen_ids.add(user_id)
            normalized_ids.append(user_id)

        invalid_ids = [user_id for user_id in normalized_ids if user_id not in self.allowed_contributor_ids]
        if invalid_ids:
            raise forms.ValidationError("Select a valid choice. One or more contributors are not available.")

        return User.objects.filter(id__in=normalized_ids).order_by("username")

    def clean(self):
        cleaned_data = super().clean()
        date_received = cleaned_data.get("date_received")
        expected_completion_date = cleaned_data.get("expected_completion_date")
        completion_date = cleaned_data.get("completion_date")

        if date_received and expected_completion_date and expected_completion_date < date_received:
            self.add_error("expected_completion_date", "Expected completion date cannot be before date received.")
        if date_received and completion_date and completion_date < date_received:
            self.add_error("completion_date", "Completion date cannot be before date received.")

        contributors = cleaned_data.get("contributors")
        technician_ids = [
            technician.id
            for technician in (cleaned_data.get("assigned_technician"), cleaned_data.get("assistant_technician"))
            if technician is not None
        ]
        if contributors is not None and technician_ids:
            existing_ids = set(contributors.values_list("id", flat=True))
            merged_ids = sorted(existing_ids | set(technician_ids))
            cleaned_data["contributors"] = User.objects.filter(id__in=merged_ids).order_by("username")
        return cleaned_data


class AttachmentUploadForm(forms.Form):
    file = forms.FileField()
