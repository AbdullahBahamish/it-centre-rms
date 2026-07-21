from django.contrib import messages
from django.contrib.auth.decorators import login_required
import mimetypes
from pathlib import PurePosixPath
from urllib.parse import quote

from django.core.exceptions import SuspiciousFileOperation
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render

from apps.core.services import AccessService
from apps.core.security import log_security_failure
from apps.records.models import RecordAttachment
from apps.records.application.use_cases import (
    AllowedAttachmentExtensionsUseCase,
    CreateRecordUseCase,
    DeleteRecordUseCase,
    GetRecordDetailUseCase,
    ListRecordsUseCase,
    RecordFormContextUseCase,
    UpdateRecordUseCase,
    UploadAttachmentUseCase,
)
from apps.records.presentation.forms import AttachmentUploadForm, RecordForm


RECORD_FORM_PAYLOAD_FIELDS = (
    "asset_tag",
    "device_type",
    "manufacturer",
    "model",
    "serial_number",
    "operating_system",
    "system_architecture",
    "cpu",
    "ram",
    "storage",
    "location",
    "department",
    "room",
    "device_owner",
    "maintenance_type",
    "problem_category",
    "priority",
    "reported_by",
    "assigned_technician",
    "assistant_technician",
    "support_team",
    "date_received",
    "expected_completion_date",
    "maintenance_status",
    "diagnosis",
    "repair_performed",
    "software_installed",
    "drivers_installed",
    "parts_replaced",
    "bios_updated",
    "firmware_updated",
    "testing_results",
    "remarks",
    "completed_by",
    "completion_date",
    "final_device_status",
)


def _record_form_payload(form):
    payload = {
        "title": form.cleaned_data["title"],
        "record_type_name": form.cleaned_data["record_type"].name,
        "category_id": form.cleaned_data["category"].id,
        "retention_until": form.cleaned_data["retention_until"],
        "contributor_ids": list(form.cleaned_data["contributors"].values_list("id", flat=True)),
        "allow_all_contributors": form.cleaned_data["allow_all_contributors"],
        "case_description": form.cleaned_data["case_description"],
    }
    payload.update({field: form.cleaned_data.get(field) for field in RECORD_FORM_PAYLOAD_FIELDS})
    return payload


def record_list(request):
    context_result = RecordFormContextUseCase().execute(user=request.user)
    records_result = ListRecordsUseCase().execute(user=request.user)
    if not context_result.success or not records_result.success:
        raise Http404
    context_data = context_result.payload
    return render(
        request,
        "records/record_list.html",
        {
            "records": records_result.payload,
            "can_create_records": any(
                AccessService.can(request.user, "create_record", category)
                for category in context_data["categories"]
            ),
        },
    )


def record_create(request):
    context_result = RecordFormContextUseCase().execute(user=request.user)
    if not context_result.success:
        raise Http404
    context_data = context_result.payload
    if request.method == "POST":
        form = RecordForm(
            request.POST,
            categories=context_data["categories"],
            record_types=context_data["record_types"],
        )
        if form.is_valid():
            result = CreateRecordUseCase().execute(
                user=request.user,
                payload=_record_form_payload(form),
            )
            if result.success:
                return redirect("record_detail", record_id=result.payload.id)
            if result.error == "invalid_contributors":
                form.add_error(None, "Contributors must already be authorized for the selected category.")
            else:
                raise Http404
    else:
        form = RecordForm(categories=context_data["categories"], record_types=context_data["record_types"])
    return render(request, "records/record_form.html", {"form": form, "record": None})


def record_detail(request, record_id):
    result = GetRecordDetailUseCase().execute(user=request.user, record_id=record_id)
    if not result.success:
        raise Http404
    record = result.payload
    extensions_result = AllowedAttachmentExtensionsUseCase().execute()
    return render(
        request,
        "records/record_detail.html",
        {
            "record": record,
            "can_update_record": AccessService.can(request.user, "update_record", record),
            "can_delete_record": AccessService.can(request.user, "delete_record", record),
            "allowed_attachment_extensions_text": extensions_result.payload if extensions_result.success else "",
        },
    )


def record_update(request, record_id):
    detail_result = GetRecordDetailUseCase().execute(user=request.user, record_id=record_id)
    if not detail_result.success:
        raise Http404
    record = detail_result.payload
    context_result = RecordFormContextUseCase().execute(user=request.user, record=record)
    if not context_result.success:
        raise Http404
    context_data = context_result.payload

    initial = {
        "title": record.title,
        "record_type": record.record_type_id,
        "category": record.category_id,
        "retention_until": record.retention_until,
        "allow_all_contributors": record.allow_all_contributors,
        "contributors": record.contributors.all(),
        "case_description": record.case_description,
        "maintenance_type": record.maintenance_type,
        "problem_category": record.problem_category,
        "priority": record.priority,
        "reported_by": record.reported_by,
        "assigned_technician": record.assigned_technician_id,
        "assistant_technician": record.assistant_technician_id,
        "support_team": record.support_team,
        "date_received": record.date_received,
        "expected_completion_date": record.expected_completion_date,
        "maintenance_status": record.maintenance_status,
        "diagnosis": record.diagnosis,
        "repair_performed": record.repair_performed,
        "software_installed": record.software_installed,
        "drivers_installed": record.drivers_installed,
        "parts_replaced": record.parts_replaced,
        "bios_updated": record.bios_updated,
        "firmware_updated": record.firmware_updated,
        "testing_results": record.testing_results,
        "remarks": record.remarks,
        "completed_by": record.completed_by_id,
        "completion_date": record.completion_date,
        "final_device_status": record.final_device_status,
    }
    if record.asset:
        initial.update(
            {
                "asset_tag": record.asset.asset_tag,
                "device_type": record.asset.device_type,
                "manufacturer": record.asset.manufacturer,
                "model": record.asset.model,
                "serial_number": record.asset.serial_number,
                "operating_system": record.asset.operating_system,
                "system_architecture": record.asset.system_architecture,
                "cpu": record.asset.cpu,
                "ram": record.asset.ram,
                "storage": record.asset.storage,
                "location": record.asset.location,
                "department": record.asset.department,
                "room": record.asset.room,
                "device_owner": record.asset.device_owner,
            }
        )

    if request.method == "POST":
        form = RecordForm(
            request.POST,
            categories=context_data["categories"],
            record_types=context_data["record_types"],
            record=record,
        )
        if form.is_valid():
            result = UpdateRecordUseCase().execute(
                user=request.user,
                record_id=record_id,
                payload=_record_form_payload(form),
            )
            if result.success:
                return redirect("record_detail", record_id=result.payload.id)
            if result.error == "invalid_contributors":
                form.add_error(None, "Contributors must already be authorized for the selected category.")
            else:
                raise Http404
    else:
        form = RecordForm(
            initial=initial,
            categories=context_data["categories"],
            record_types=context_data["record_types"],
            record=record,
        )

    return render(request, "records/record_form.html", {"form": form, "record": record})


def upload_attachment(request, record_id):
    if request.method != "POST":
        return redirect("record_detail", record_id=record_id)

    form = AttachmentUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Please choose a file to upload.")
        return redirect("record_detail", record_id=record_id)

    result = UploadAttachmentUseCase().execute(
        user=request.user,
        record_id=record_id,
        upload=form.cleaned_data["file"],
    )
    if not result.success:
        if result.error == "invalid_upload":
            messages.error(request, result.payload or "Unsupported or invalid file.")
        else:
            raise Http404

    return redirect("record_detail", record_id=record_id)


def record_delete(request, record_id):
    detail_result = GetRecordDetailUseCase().execute(user=request.user, record_id=record_id)
    if not detail_result.success:
        raise Http404
    record = detail_result.payload
    if request.method == "POST":
        result = DeleteRecordUseCase().execute(user=request.user, record_id=record_id)
        if not result.success:
            raise Http404
        return redirect("record_list")
    return render(request, "records/record_confirm_delete.html", {"record": record})


@login_required
def download_record_pdf(request, record_id):
    detail_result = GetRecordDetailUseCase().execute(user=request.user, record_id=record_id)
    if not detail_result.success:
        raise Http404
    return _secure_file_response(file_field=detail_result.payload.pdf_file)


@login_required
def download_attachment(request, attachment_id):
    attachment = RecordAttachment.objects.select_related("record").filter(pk=attachment_id).first()
    if not attachment or not AccessService.can(request.user, "view_record", attachment.record):
        raise Http404
    return _secure_file_response(file_field=attachment.file, download_name=attachment.display_name)


def _secure_file_response(*, file_field, download_name=None):
    try:
        if not file_field or not getattr(file_field, "name", ""):
            raise Http404
        normalized = PurePosixPath(file_field.name)
        if any(part == ".." for part in normalized.parts):
            raise SuspiciousFileOperation("Invalid file path.")
        if not file_field.storage.exists(file_field.name):
            raise Http404

        safe_name = PurePosixPath(download_name or normalized.name).name
        guessed_type, _ = mimetypes.guess_type(safe_name)
        content_type = guessed_type or "application/octet-stream"
        response = FileResponse(
            file_field.open("rb"),
            as_attachment=True,
            filename=safe_name,
            content_type=content_type,
        )
        response["Content-Type"] = content_type
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(safe_name)}"
        return response
    except Http404:
        raise
    except Exception:
        log_security_failure(action="secure_file_response", reason="exception", target=getattr(file_field, "name", None))
        raise Http404
