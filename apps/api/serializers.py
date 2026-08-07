from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.core.services import AccessService
from apps.records.application.use_cases import CreateRecordUseCase, UpdateRecordUseCase
from apps.records.models import Category, ITAsset, Record, RecordAttachment, RecordType


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    role = serializers.CharField(source="userprofile.role.name", read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "is_active", "role")
        read_only_fields = ("id", "username", "is_active", "role")


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "allowed_roles", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class RecordTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecordType
        fields = ("name", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")


class ITAssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ITAsset
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class RecordAttachmentSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = RecordAttachment
        fields = ("id", "record", "file", "display_name", "uploaded_at")
        read_only_fields = ("id", "display_name", "uploaded_at")


class RecordSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    attachments = RecordAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Record
        exclude = ("pdf_file",)
        read_only_fields = ("id", "created_by", "created_at", "updated_at", "attachments")

    def validate_category(self, category):
        request = self.context["request"]
        if not AccessService.can(request.user, "access_category", category):
            raise serializers.ValidationError("You do not have access to this category.")
        return category

    def create(self, validated_data):
        result = CreateRecordUseCase().execute(
            user=self.context["request"].user,
            payload=self._use_case_payload(validated_data),
        )
        if not result.success:
            raise serializers.ValidationError({"detail": result.error or "Record could not be created."})
        return result.payload

    def update(self, instance, validated_data):
        result = UpdateRecordUseCase().execute(
            user=self.context["request"].user,
            record_id=instance.pk,
            payload=self._use_case_payload(validated_data, instance=instance),
        )
        if not result.success:
            raise serializers.ValidationError({"detail": result.error or "Record could not be updated."})
        return result.payload

    @staticmethod
    def _use_case_payload(validated_data, instance=None):
        values = dict(validated_data)
        if instance:
            for field in ("title", "case_description", "retention_until", "allow_all_contributors", *(
                "maintenance_type", "problem_category", "priority", "reported_by", "assigned_technician",
                "assistant_technician", "support_team", "date_received", "expected_completion_date",
                "maintenance_status", "diagnosis", "repair_performed", "software_installed", "drivers_installed",
                "parts_replaced", "bios_updated", "firmware_updated", "testing_results", "remarks", "completed_by",
                "completion_date", "final_device_status",
            )):
                values.setdefault(field, getattr(instance, field))
        else:
            for field in (
                "maintenance_type", "problem_category", "priority", "reported_by", "support_team",
                "maintenance_status", "diagnosis", "repair_performed", "software_installed", "drivers_installed",
                "parts_replaced", "testing_results", "remarks", "final_device_status",
            ):
                values.setdefault(field, "")
            for field in ("assigned_technician", "assistant_technician", "completed_by", "date_received", "expected_completion_date", "completion_date"):
                values.setdefault(field, None)
            values.setdefault("bios_updated", False)
            values.setdefault("firmware_updated", False)
        category = values.pop("category", None) or (instance.category if instance else None)
        record_type = values.pop("record_type", None) or (instance.record_type if instance else None)
        contributors = values.pop("contributors", None)
        asset = values.pop("asset", None)
        payload = values
        payload.update(
            {
                "category_id": category.pk if category else None,
                "record_type_name": record_type.name if record_type else None,
                "contributor_ids": [user.pk for user in (contributors if contributors is not None else (instance.contributors.all() if instance else []))],
                "allow_all_contributors": values.get("allow_all_contributors", instance.allow_all_contributors if instance else False),
            }
        )
        if asset:
            for field in (
                "asset_tag", "barcode", "device_type", "manufacturer", "model", "serial_number",
                "operating_system", "system_architecture", "cpu", "ram", "storage", "location",
                "department", "room", "assigned_user", "purchase_date", "warranty_expiry", "status", "notes",
            ):
                payload[field] = getattr(asset, field)
        elif instance and instance.asset:
            for field in (
                "asset_tag", "barcode", "device_type", "manufacturer", "model", "serial_number",
                "operating_system", "system_architecture", "cpu", "ram", "storage", "location",
                "department", "room", "assigned_user", "purchase_date", "warranty_expiry", "status", "notes",
            ):
                payload[field] = getattr(instance.asset, field)
        return payload
