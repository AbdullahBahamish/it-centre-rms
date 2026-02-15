from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import get_user_model

from .services import RecordService
from .models import Record

from django.shortcuts import get_object_or_404

User = get_user_model()


# @login_required
def record_list(request):
    records = RecordService.list_records()
    return render(request, "records/record_list.html", {
        "records": records
    })


@login_required
def record_create(request):
    if request.method == "POST":
        title = request.POST.get("title")
        record_type = request.POST.get("record_type")
        case_description = request.POST.get("case_description", "")
        contributors_ids = request.POST.getlist("contributors")

        contributors = User.objects.filter(id__in=contributors_ids)

        RecordService.create_record(
            title=title,
            record_type=record_type,
            created_by=request.user,
            contributors=contributors,
            case_description=case_description,
        )

        return redirect("record_list")

    users = User.objects.all()
    return render(request, "records/record_form.html", {
        "users": users
    })


# @login_required
def record_detail(request, record_id):
    record = get_object_or_404(Record, id=record_id)

    return render(request, "records/record_detail.html", {
        "record": record,
    })


@login_required
def upload_attachment(request, record_id):
    record = get_object_or_404(Record, id=record_id)

    if request.method == "POST" and request.FILES.get("file"):
        RecordAttachment.objects.create(
            record=record,
            file=request.FILES["file"],
        )

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