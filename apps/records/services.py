from typing import Iterable, Optional

from django.contrib.auth import get_user_model

from .models import Category, Record
from .pdf import generate_record_pdf

User = get_user_model()


def _normalize_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


class RecordService:
    @staticmethod
    def create_record(
        *,
        title: str,
        record_type: str,
        category: Optional[Category] = None,
        created_by: Optional[User],
        contributors: Iterable[User] = (),
        case_description: str = "",
        retention_until=None,
    ) -> Record:
        record = Record.objects.create(
            title=_normalize_text(title),
            record_type=_normalize_text(record_type),
            created_by=created_by,
            case_description=(case_description or "").strip(),
            retention_until=retention_until,
        )
        if category is not None:
            record.category = category
            record.save(update_fields=["category", "updated_at"])
        if contributors:
            record.contributors.set(contributors)

        generate_record_pdf(record, record.created_at)
        record.save(update_fields=["pdf_file", "updated_at"])
        return record

    @staticmethod
    def update_record(
        *,
        record: Record,
        title: str,
        record_type: str,
        category: Category,
        contributors: Iterable[User],
        case_description: str = "",
        retention_until=None,
        regenerate_pdf: bool = True,
    ) -> Record:
        record.title = _normalize_text(title)
        record.record_type = _normalize_text(record_type)
        record.category = category
        record.case_description = (case_description or "").strip()
        record.retention_until = retention_until
        record.save()
        record.contributors.set(contributors)
        if regenerate_pdf:
            generate_record_pdf(record)
            record.save(update_fields=["pdf_file", "updated_at"])
        return record

    @staticmethod
    def list_records():
        return Record.objects.select_related("category", "created_by").prefetch_related("contributors")

    @staticmethod
    def get_record(record_id: int) -> Record:
        return Record.objects.select_related("category", "created_by").prefetch_related("contributors").get(id=record_id)

    @staticmethod
    def archive_record(record: Record) -> None:
        record.status = "archived"
        record.save(update_fields=["status", "updated_at"])
        generate_record_pdf(record)
        record.save(update_fields=["pdf_file", "updated_at"])
