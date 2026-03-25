import re
from datetime import datetime

from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.text import slugify


def _timestamp_for_filename(ts):
    if ts is None:
        ts = timezone.now()
    return ts.strftime("%Y%m%d_%H%M%S_") + f"{ts.microsecond // 1000:03d}"


def sanitize_title(title):
    cleaned = slugify((title or "").strip())
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", cleaned).strip("_")
    return cleaned


def build_record_pdf_filename(record, ts=None):
    timestamp = _timestamp_for_filename(ts)
    safe_title = sanitize_title(record.title)
    if safe_title:
        return f"{safe_title}_{timestamp}.pdf"
    return f"record_{record.pk}_{timestamp}.pdf"


def _escape_pdf_text(value):
    text = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text.replace("\n", "\\n")


def render_record_pdf_bytes(record):
    created_text = timezone.localtime(record.created_at).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    lines = [
        "Record Management System",
        f"Title: {record.title}",
        f"Type: {record.record_type}",
        f"Category: {record.category.name}",
        f"Status: {record.status}",
        f"Created At: {created_text}",
        "",
        "Description:",
        record.case_description or "-",
    ]
    text_ops = ["BT", "/F1 12 Tf", "50 780 Td", "14 TL"]
    for line in lines:
        text_ops.append(f"({_escape_pdf_text(line)}) Tj")
        text_ops.append("T*")
    text_ops.append("ET")
    stream_content = "\n".join(text_ops).encode("latin-1", errors="replace")

    objects = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n")
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
    )
    objects.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objects.append(
        b"5 0 obj\n<< /Length "
        + str(len(stream_content)).encode()
        + b" >>\nstream\n"
        + stream_content
        + b"\nendstream\nendobj\n"
    )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)
    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
    )
    return bytes(pdf)


def generate_record_pdf(record, ts=None):
    timestamp_source = ts or timezone.now()
    filename = build_record_pdf_filename(record, timestamp_source)
    pdf_bytes = render_record_pdf_bytes(record)
    record.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
