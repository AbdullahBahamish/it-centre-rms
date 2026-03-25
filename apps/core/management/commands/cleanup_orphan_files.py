import logging
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.records.models import Record, RecordAttachment


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Remove unreferenced files from MEDIA_ROOT."

    def handle(self, *args, **options):
        # Run periodically:
        # python manage.py cleanup_orphan_files
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            self.stdout.write(self.style.WARNING("MEDIA_ROOT does not exist."))
            return

        referenced_files = self._referenced_files()
        deleted = 0

        for path in media_root.rglob("*"):
            if not path.is_file():
                continue

            relative_name = path.relative_to(media_root).as_posix()
            if relative_name in referenced_files:
                continue

            try:
                path.unlink()
                deleted += 1
            except OSError:
                logger.exception("Orphan file cleanup failed", extra={"path": relative_name})

        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} orphan file(s)."))

    @staticmethod
    def _referenced_files():
        referenced = set(
            Record.objects.exclude(pdf_file="").values_list("pdf_file", flat=True)
        )
        referenced.update(
            RecordAttachment.objects.exclude(file="").values_list("file", flat=True)
        )
        return {name for name in referenced if name}
