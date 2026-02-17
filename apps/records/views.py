from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .services import RecordService
from .models import Record, RecordAttachment

User = get_user_model()


# @login_required
def record_list(request):
    records = RecordService.list_records()
    return render(request, "records/record_list.html", {
        "records": records
    })


# Remove @login_required decorator
def record_create(request):
    if request.method == "POST":
        title = request.POST.get("title")
        record_type = request.POST.get("record_type")
        case_description = request.POST.get("case_description", "")
        contributors_ids = request.POST.getlist("contributors")

        # Validate required fields
        if not title or not record_type:
            users = User.objects.all()
            return render(request, "records/record_form.html", {
                "users": users,
                "error": _("Title and Record Type are required fields.")
            })

        contributors = User.objects.filter(id__in=contributors_ids)

        # Set created_by to the logged-in user if authenticated, otherwise None
        created_by = request.user if request.user.is_authenticated else None

        RecordService.create_record(
            title=title,
            record_type=record_type,
            created_by=created_by,  # Can now be None
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


# @login_required
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