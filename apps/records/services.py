# apps/records/services.py

from typing import Iterable, Optional
from django.contrib.auth import get_user_model
from .models import Record

User = get_user_model()


def _normalize_text(value: str) -> str:
    return " ".join((value or "").split()).strip()


class RecordService:
    @staticmethod
    def create_record(
        *,
        title: str,
        record_type: str,
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

        if contributors:
            record.contributors.set(contributors)

        return record

    @staticmethod
    def list_records():
        return Record.objects.all()

    @staticmethod
    def get_record(record_id: int) -> Record:
        return Record.objects.get(id=record_id)

    @staticmethod
    def archive_record(record: Record) -> None:
        record.status = "archived"
        record.save(update_fields=["status"])
