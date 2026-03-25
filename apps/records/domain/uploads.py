from pathlib import Path

from django.core.exceptions import ValidationError

ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".png", ".jpg", ".jpeg"}
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024

MIME_BY_EXTENSION = {
    ".pdf": {"application/pdf"},
    ".doc": {"application/msword", "application/octet-stream"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    },
    ".txt": {"text/plain"},
    ".png": {"image/png"},
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
}


def allowed_extensions_text() -> str:
    return ", ".join(sorted(ext.lstrip(".").upper() for ext in ALLOWED_ATTACHMENT_EXTENSIONS))


def _sniff_mime(sample: bytes):
    if sample.startswith(b"%PDF-"):
        return "application/pdf"
    if sample.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if sample.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if sample.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/msword"
    if sample.startswith(b"PK\x03\x04"):
        return "application/zip"
    try:
        sample.decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError:
        return "application/octet-stream"


def validate_upload(upload):
    extension = Path(upload.name).suffix.lower()
    if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError(f"Unsupported file format. Allowed formats: {allowed_extensions_text()}")
    if upload.size > MAX_ATTACHMENT_SIZE_BYTES:
        raise ValidationError("File is too large. Maximum size is 10 MB.")

    position = upload.tell()
    sample = upload.read(2048)
    upload.seek(position)
    sniffed_mime = _sniff_mime(sample)
    if sniffed_mime not in MIME_BY_EXTENSION.get(extension, set()):
        raise ValidationError("File content does not match file type.")
