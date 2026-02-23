from pathlib import Path
from uuid import uuid4

from django.utils.text import slugify


def record_attachment_path(instance, filename):
    """
    backup/records/<record_type>/<record_id>/<safe-name>-<uuid>.<ext>
    """
    record = instance.record
    category = slugify(record.record_type or "general") or "general"
    record_id = record.id

    source_name = Path(filename)
    ext = source_name.suffix.lower()
    base_name = slugify(source_name.stem) or "file"
    safe_filename = f"{base_name}-{uuid4().hex[:8]}{ext}"

    return Path(
        "backup",
        "records",
        category,
        str(record_id),
        safe_filename,
    )
