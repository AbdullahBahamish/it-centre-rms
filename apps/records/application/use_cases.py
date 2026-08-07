from django.core.exceptions import ValidationError
from django.db import transaction

from apps.records.domain.uploads import allowed_extensions_text, validate_upload
from apps.core.services import AccessService
from apps.core.security import ServiceResult, log_security_event, log_security_failure
from apps.records.infrastructure.repositories import (
    AttachmentRepository,
    CategoryRepository,
    ITAssetRepository,
    RecordRepository,
    RecordTypeRepository,
    UserRepository,
)
from apps.records.pdf import generate_record_pdf


def _normalize_text(value: str):
    return " ".join((value or "").split()).strip()


DEVICE_FIELDS = (
    "asset_tag",
    "barcode",
    "device_type",
    "manufacturer",
    "model",
    "serial_number",
    "operating_system",
    "system_architecture",
    "cpu",
    "ram",
    "storage",
    "location",
    "department",
    "room",
    "assigned_user",
    "purchase_date",
    "warranty_expiry",
    "status",
    "notes",
)


class LookupAssetUseCase:
    def execute(self, *, asset_tag):
        try:
            asset = ITAssetRepository().get_by_asset_tag(asset_tag)
            if not asset:
                return ServiceResult(success=False, error="not_found")
            
            payload = {
                "id": asset.id,
                "asset_tag": asset.asset_tag,
                "barcode": asset.barcode,
                "device_type": asset.device_type,
                "manufacturer": asset.manufacturer,
                "model": asset.model,
                "serial_number": asset.serial_number,
                "operating_system": asset.operating_system,
                "system_architecture": asset.system_architecture,
                "cpu": asset.cpu,
                "ram": asset.ram,
                "storage": asset.storage,
                "location": asset.location,
                "department": asset.department,
                "room": asset.room,
                "assigned_user": asset.assigned_user,
                "purchase_date": asset.purchase_date.isoformat() if asset.purchase_date else "",
                "warranty_expiry": asset.warranty_expiry.isoformat() if asset.warranty_expiry else "",
                "status": asset.status,
                "notes": asset.notes,
            }
            return ServiceResult(success=True, payload=payload)
        except Exception:
            return ServiceResult(success=False, error="exception")

MAINTENANCE_FIELDS = (
    "maintenance_type",
    "problem_category",
    "priority",
    "reported_by",
    "assigned_technician",
    "assistant_technician",
    "support_team",
    "date_received",
    "expected_completion_date",
    "maintenance_status",
    "diagnosis",
    "repair_performed",
    "software_installed",
    "drivers_installed",
    "parts_replaced",
    "bios_updated",
    "firmware_updated",
    "testing_results",
    "remarks",
    "completed_by",
    "completion_date",
    "final_device_status",
)


def _asset_payload(payload):
    return {field: payload.get(field) for field in DEVICE_FIELDS}


def _maintenance_payload(payload):
    return {field: payload.get(field) for field in MAINTENANCE_FIELDS}

class ListRecordsUseCase:
    def execute(self, *, user):
        try:
            records = RecordRepository().list_records()
            visible = [record for record in records if AccessService.can(user, "view_record", record)]
            return ServiceResult(success=True, payload=visible)
        except Exception:
            log_security_failure(action="list_records", actor=user, reason="exception")
            return ServiceResult(success=False, error="permission_denied")


class RecordFormContextUseCase:
    def execute(self, *, user, record=None):
        try:
            categories = []
            for category in CategoryRepository().all_categories():
                if AccessService.can(user, "access_category", category):
                    categories.append(category)
            return ServiceResult(
                success=True,
                payload={
                    "categories": categories,
                    "record_types": list(RecordTypeRepository().all_record_types()),
                    "record": record,
                },
            )
        except Exception:
            log_security_failure(action="record_form_context", actor=user, reason="exception")
            return ServiceResult(success=False, error="permission_denied")


class CreateRecordUseCase:
    @transaction.atomic
    def execute(self, *, user, payload):
        try:
            category = CategoryRepository().get_by_id(payload.get("category_id"))
            if not category:
                return ServiceResult(success=False, error="not_found", status_code=404)

            if not AccessService.can(user, "create_record", category):
                log_security_event(action="create_record", actor=user, target=getattr(category, "pk", None), result="denied", reason="permission_denied")
                return ServiceResult(success=False, error="permission_denied")

            record_type = RecordTypeRepository().get_by_name(payload.get("record_type_name"))
            if not record_type:
                return ServiceResult(success=False, error="not_found", status_code=404)

            contributors = self._validated_contributors(
                category=category,
                contributor_ids=payload.get("contributor_ids", []),
                allow_all_contributors=payload.get("allow_all_contributors", False),
            )
            if not contributors.success:
                return contributors

            asset = ITAssetRepository().upsert_from_payload(_asset_payload(payload))
            record = RecordRepository().create(
                title=_normalize_text(payload.get("title", "")),
                record_type=record_type,
                category=category,
                created_by=user if getattr(user, "is_authenticated", False) else None,
                asset=asset,
                case_description=(payload.get("case_description") or "").strip(),
                retention_until=payload.get("retention_until"),
                allow_all_contributors=payload.get("allow_all_contributors", False),
                **_maintenance_payload(payload),
            )
            RecordRepository().set_contributors(record=record, contributors=contributors.payload)
            generate_record_pdf(record, record.created_at)
            record.save(update_fields=["pdf_file", "updated_at"])
            log_security_event(action="create_record", actor=user, target=record.pk, result="allowed", reason="created")
            return ServiceResult(success=True, payload=record)
        except Exception:
            log_security_failure(action="create_record", actor=user, reason="exception")
            return ServiceResult(success=False, error="permission_denied")

    @staticmethod
    def _validated_contributors(*, category, contributor_ids, allow_all_contributors=False):
        try:
            contributor_ids = [value for value in (contributor_ids or []) if str(value).isdigit()]
            contributors = list(UserRepository().users_by_ids(contributor_ids))
            if allow_all_contributors:
                return ServiceResult(success=True, payload=contributors)

            invalid = [user.pk for user in contributors if not AccessService.can(user, "access_category", category)]
            if invalid:
                return ServiceResult(success=False, error="invalid_contributors")
            return ServiceResult(success=True, payload=contributors)
        except Exception:
            log_security_failure(action="validate_contributors", target=getattr(category, "pk", None), reason="exception")
            return ServiceResult(success=False, error="invalid_contributors")


class GetRecordDetailUseCase:
    def execute(self, *, user, record_id: int):
        try:
            record = RecordRepository().get_by_id(record_id)
            if not record or not AccessService.can(user, "view_record", record):
                return ServiceResult(success=False, error="not_found", status_code=404)
            return ServiceResult(success=True, payload=record)
        except Exception:
            log_security_failure(action="get_record_detail", actor=user, target=record_id, reason="exception")
            return ServiceResult(success=False, error="not_found", status_code=404)


class UpdateRecordUseCase:
    @transaction.atomic
    def execute(self, *, user, record_id: int, payload):
        try:
            record = RecordRepository().get_by_id(record_id)
            if not record or not AccessService.can(user, "update_record", record):
                return ServiceResult(success=False, error="not_found", status_code=404)

            category = CategoryRepository().get_by_id(payload.get("category_id"))
            if not category or not AccessService.can(user, "access_category", category):
                return ServiceResult(success=False, error="not_found", status_code=404)

            record_type = RecordTypeRepository().get_by_name(payload.get("record_type_name"))
            if not record_type:
                return ServiceResult(success=False, error="not_found", status_code=404)

            contributors = CreateRecordUseCase._validated_contributors(
                category=category,
                contributor_ids=payload.get("contributor_ids", []),
                allow_all_contributors=payload.get("allow_all_contributors", False),
            )
            if not contributors.success:
                return contributors

            asset = ITAssetRepository().upsert_from_payload(_asset_payload(payload))
            record = RecordRepository().update(
                record=record,
                title=_normalize_text(payload.get("title", "")),
                record_type=record_type,
                category=category,
                asset=asset,
                case_description=(payload.get("case_description") or "").strip(),
                retention_until=payload.get("retention_until"),
                allow_all_contributors=payload.get("allow_all_contributors", False),
                **_maintenance_payload(payload),
            )
            RecordRepository().set_contributors(record=record, contributors=contributors.payload)
            generate_record_pdf(record)
            record.save(update_fields=["pdf_file", "updated_at"])
            log_security_event(action="update_record", actor=user, target=record.pk, result="allowed", reason="updated")
            return ServiceResult(success=True, payload=record)
        except Exception:
            log_security_failure(action="update_record", actor=user, target=record_id, reason="exception")
            return ServiceResult(success=False, error="permission_denied")


class UploadAttachmentUseCase:
    @transaction.atomic
    def execute(self, *, user, record_id: int, upload):
        try:
            record = RecordRepository().get_by_id(record_id)
            if not record or not AccessService.can(user, "update_record", record):
                return ServiceResult(success=False, error="not_found", status_code=404)

            validate_upload(upload)
            attachment = AttachmentRepository().create(record=record, upload=upload)
            log_security_event(action="upload_attachment", actor=user, target=record.pk, result="allowed", reason="created")
            return ServiceResult(success=True, payload=attachment)
        except ValidationError as exc:
            return ServiceResult(
                success=False,
                error="invalid_upload",
                payload=exc.messages[0] if exc.messages else "Unsupported or invalid file.",
            )
        except Exception:
            log_security_failure(action="upload_attachment", actor=user, target=record_id, reason="exception")
            return ServiceResult(success=False, error="permission_denied")


class DeleteRecordUseCase:
    @transaction.atomic
    def execute(self, *, user, record_id: int):
        try:
            record = RecordRepository().get_by_id(record_id)
            if not record or not AccessService.can(user, "delete_record", record):
                return ServiceResult(success=False, error="not_found", status_code=404)

            RecordRepository().delete(record=record)
            log_security_event(action="delete_record", actor=user, target=record_id, result="allowed", reason="deleted")
            return ServiceResult(success=True)
        except Exception:
            log_security_failure(action="delete_record", actor=user, target=record_id, reason="exception")
            return ServiceResult(success=False, error="permission_denied")


class AllowedAttachmentExtensionsUseCase:
    def execute(self):
        return ServiceResult(success=True, payload=allowed_extensions_text())
