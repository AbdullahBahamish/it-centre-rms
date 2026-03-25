from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver
import logging

from .models import Record, RecordAttachment


logger = logging.getLogger(__name__)


def _delete_file(field_file):
    if not field_file or not field_file.name:
        return
    storage = field_file.storage
    name = field_file.name
    try:
        if storage.exists(name):
            storage.delete(name)
    except Exception:
        logger.exception("File deletion failed", extra={"path": name})


@receiver(pre_save, sender=Record)
def capture_old_record_pdf_on_change(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    old_file = old_instance.pdf_file
    new_file = instance.pdf_file

    if not old_file or old_file == new_file:
        return

    old_name = old_file.name
    storage = old_file.storage
    instance._old_pdf_file_name = old_name
    instance._old_pdf_storage = storage


@receiver(post_save, sender=Record)
def delete_stale_record_pdf_after_save(sender, instance, **kwargs):
    old_name = getattr(instance, "_old_pdf_file_name", None)
    storage = getattr(instance, "_old_pdf_storage", None)
    if not old_name or storage is None:
        return
    del instance._old_pdf_file_name
    del instance._old_pdf_storage

    def delete_if_stale():
        try:
            current_name = sender.objects.values_list("pdf_file", flat=True).get(pk=instance.pk)
        except sender.DoesNotExist:
            return

        if current_name != old_name:
            try:
                if storage.exists(old_name):
                    storage.delete(old_name)
            except Exception:
                logger.exception("Stale file deletion failed", extra={"path": old_name})

    transaction.on_commit(delete_if_stale)


@receiver(post_delete, sender=Record)
def delete_record_pdf_on_delete(sender, instance, **kwargs):
    file = instance.pdf_file
    transaction.on_commit(lambda: _delete_file(file))


@receiver(post_delete, sender=RecordAttachment)
def delete_attachment_file_on_delete(sender, instance, **kwargs):
    file = instance.file
    transaction.on_commit(lambda: _delete_file(file))
