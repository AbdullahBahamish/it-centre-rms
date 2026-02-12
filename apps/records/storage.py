from pathlib import Path


def record_attachment_path(instance, filename):
    """
    backup/records/<record_type>/<record_id>/<filename>
    """
    record = instance.record
    category = record.record_type.replace(" ", "_")
    record_id = record.id

    return Path(
        "backup",
        "records",
        category,
        str(record_id),
        filename,
    )
