from django.core.exceptions import ValidationError
from django.db import transaction

from apps.records.domain.uploads import allowed_extensions_text, validate_upload
from apps.core.services import AccessService
from apps.core.security import ServiceResult, log_security_event, log_security_failure
from apps.records.infrastructure.repositories import (
    AttachmentRepository,
    CategoryRepository,
    RecordRepository,
    UserRepository,
)
from apps.records.pdf import generate_record_pdf


def _normalize_text(value: str):
    return " ".join((value or "").split()).strip()

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
                    "users": UserRepository().all_users(),
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

            contributors = self._validated_contributors(
                category=category,
                contributor_ids=payload.get("contributor_ids", []),
            )
            if not contributors.success:
                return contributors

            record = RecordRepository().create(
                title=_normalize_text(payload.get("title", "")),
                record_type=_normalize_text(payload.get("record_type", "")),
                category=category,
                created_by=user if getattr(user, "is_authenticated", False) else None,
                case_description=(payload.get("case_description") or "").strip(),
                retention_until=payload.get("retention_until"),
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
    def _validated_contributors(*, category, contributor_ids):
        try:
            contributor_ids = [value for value in (contributor_ids or []) if str(value).isdigit()]
            contributors = list(UserRepository().users_by_ids(contributor_ids))
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

            contributors = CreateRecordUseCase._validated_contributors(
                category=category,
                contributor_ids=payload.get("contributor_ids", []),
            )
            if not contributors.success:
                return contributors

            record = RecordRepository().update(
                record=record,
                title=_normalize_text(payload.get("title", "")),
                record_type=_normalize_text(payload.get("record_type", "")),
                category=category,
                case_description=(payload.get("case_description") or "").strip(),
                retention_until=payload.get("retention_until"),
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
