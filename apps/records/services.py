# apps/records/services.py

from typing import Iterable
from django.contrib.auth import get_user_model
from .models import Record

User = get_user_model()


class RecordService:
    @staticmethod
    def create_record(
        *,
        title: str,
        record_type: str,
        created_by: User,
        contributors: Iterable[User] = (),
        case_description: str = "",
        retention_until=None,
    ) -> Record:
        record = Record.objects.create(
            title=title,
            record_type=record_type,
            created_by=created_by,
            case_description=case_description,
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
