from django.contrib.auth import get_user_model

from apps.core.models import SystemSettings
from apps.core.rbac import normalize_role_code
from apps.core.services import AccessService
from apps.records.models import Category, Record, RecordAttachment

User = get_user_model()


class ActorRepository:
    @staticmethod
    def to_actor(user):
        return {
            "id": getattr(user, "id", None),
            "is_authenticated": bool(getattr(user, "is_authenticated", False)),
            "is_superuser": bool(getattr(user, "is_superuser", False)),
            "role": AccessService.get_role_name(user),
            "permissions": AccessService.get_permissions(user),
        }


class SystemSettingsRepository:
    @staticmethod
    def get_policy():
        settings_obj = SystemSettings.get_solo()
        return {
            "allow_anonymous_create": settings_obj.allow_anonymous_create,
            "allow_anonymous_update": settings_obj.allow_anonymous_update,
            "allow_anonymous_delete": settings_obj.allow_anonymous_delete,
        }


class CategoryRepository:
    @staticmethod
    def all_categories():
        return Category.objects.all().prefetch_related("allowed_users")

    @staticmethod
    def get_by_id(category_id: int):
        return Category.objects.prefetch_related("allowed_users").filter(id=category_id).first()

    @staticmethod
    def to_policy_context(category):
        return {
            "id": category.id,
            "allowed_roles": [normalize_role_code(role) for role in (category.allowed_roles or [])],
            "allowed_user_ids": set(category.allowed_users.values_list("id", flat=True)),
        }


class UserRepository:
    @staticmethod
    def all_users():
        return User.objects.select_related("userprofile__role").all()

    @staticmethod
    def users_by_ids(user_ids):
        return User.objects.filter(id__in=user_ids)


class RecordRepository:
    @staticmethod
    def list_records():
        return (
            Record.objects.select_related("category", "created_by", "created_by__userprofile__role")
            .prefetch_related("contributors", "attachments")
        )

    @staticmethod
    def get_by_id(record_id: int):
        return (
            Record.objects.select_related("category", "created_by", "created_by__userprofile__role")
            .prefetch_related("contributors", "attachments")
            .filter(id=record_id)
            .first()
        )

    @staticmethod
    def to_policy_context(record):
        return {
            "id": record.id,
            "created_by_id": record.created_by_id,
            "contributor_ids": set(record.contributors.values_list("id", flat=True)),
        }

    @staticmethod
    def create(*, title, record_type, category, created_by, case_description="", retention_until=None):
        return Record.objects.create(
            title=title,
            record_type=record_type,
            category=category,
            created_by=created_by,
            case_description=case_description,
            retention_until=retention_until,
        )

    @staticmethod
    def update(*, record, title, record_type, category, case_description="", retention_until=None):
        record.title = title
        record.record_type = record_type
        record.category = category
        record.case_description = case_description
        record.retention_until = retention_until
        record.save()
        return record

    @staticmethod
    def set_contributors(*, record, contributors):
        record.contributors.set(contributors)

    @staticmethod
    def delete(*, record):
        record.delete()


class AttachmentRepository:
    @staticmethod
    def create(*, record, upload):
        return RecordAttachment.objects.create(record=record, file=upload)
