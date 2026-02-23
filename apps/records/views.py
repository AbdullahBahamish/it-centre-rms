from datetime import date
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .services import RecordService
from .models import Record, RecordAttachment

User = get_user_model()

ALLOWED_ATTACHMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt", ".png", ".jpg", ".jpeg"}
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024


def _allowed_extensions_text() -> str:
    return ", ".join(sorted(ext.lstrip(".").upper() for ext in ALLOWED_ATTACHMENT_EXTENSIONS))


def _build_record_form_context(*, users, values=None, error=None):
    return {
        "users": users,
        "error": error,
        "values": values or {},
    }


# @login_required
def record_list(request):
    records = RecordService.list_records()
    return render(request, "records/record_list.html", {
        "records": records
    })


# Remove @login_required decorator
def record_create(request):
    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        record_type = (request.POST.get("record_type") or "").strip()
        case_description = request.POST.get("case_description", "")
        retention_until_raw = (request.POST.get("retention_until") or "").strip()
        contributors_ids = request.POST.getlist("contributors")
        users = User.objects.all()
        values = {
            "title": title,
            "record_type": record_type,
            "case_description": case_description,
            "contributors_ids": contributors_ids,
            "retention_until": retention_until_raw,
        }

        # Validate required fields
        if not title or not record_type:
            return render(
                request,
                "records/record_form.html",
                _build_record_form_context(
                    users=users,
                    values=values,
                    error=_("Title and Record Type are required fields."),
                ),
            )

        retention_until = None
        if retention_until_raw:
            try:
                retention_until = date.fromisoformat(retention_until_raw)
            except ValueError:
                return render(
                    request,
                    "records/record_form.html",
                    _build_record_form_context(
                        users=users,
                        values=values,
                        error=_("Retention date format is invalid. Use YYYY-MM-DD."),
                    ),
                )

        contributors = User.objects.filter(id__in=contributors_ids)

        # Set created_by to the logged-in user if authenticated, otherwise None
        created_by = request.user if request.user.is_authenticated else None

        RecordService.create_record(
            title=title,
            record_type=record_type,
            created_by=created_by,  # Can now be None
            contributors=contributors,
            case_description=case_description,
            retention_until=retention_until,
        )

        return redirect("record_list")

    users = User.objects.all()
    return render(
        request,
        "records/record_form.html",
        _build_record_form_context(users=users),
    )


# @login_required
def record_detail(request, record_id):
    record = get_object_or_404(Record, id=record_id)

    return render(request, "records/record_detail.html", {
        "record": record,
        "allowed_attachment_extensions_text": _allowed_extensions_text(),
    })


# @login_required
def upload_attachment(request, record_id):
    record = get_object_or_404(Record, id=record_id)

    if request.method == "POST":
        upload = request.FILES.get("file")
        if not upload:
            messages.error(request, _("Please choose a file to upload."))
            return redirect("record_detail", record_id=record.id)

        extension = Path(upload.name).suffix.lower()
        if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
            messages.error(
                request,
                _(
                    "Unsupported file format. Allowed formats: %(formats)s"
                ) % {"formats": _allowed_extensions_text()},
            )
            return redirect("record_detail", record_id=record.id)

        if upload.size > MAX_ATTACHMENT_SIZE_BYTES:
            messages.error(request, _("File is too large. Maximum size is 10 MB."))
            return redirect("record_detail", record_id=record.id)

        RecordAttachment.objects.create(record=record, file=upload)

    return redirect("record_detail", record_id=record.id)


@permission_required("records.delete_record", raise_exception=True)
@login_required
def record_delete(request, record_id):
    record = get_object_or_404(Record, id=record_id)

    if request.method == "POST":
        record.delete()
        return redirect("record_list")

    return render(request, "records/record_confirm_delete.html", {
        "record": record
    })
