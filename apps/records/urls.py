from django.urls import path

from apps.records.presentation import views

urlpatterns = [
    path("", views.record_list, name="record_list"),
    path("create/", views.record_create, name="record_create"),
    path("<int:record_id>/", views.record_detail, name="record_detail"),
    path("<int:record_id>/download/pdf/", views.download_record_pdf, name="download_record_pdf"),
    path("<int:record_id>/edit/", views.record_update, name="record_update"),
    path("<int:record_id>/upload/", views.upload_attachment, name="upload_attachment"),
    path("<int:record_id>/delete/", views.record_delete, name="record_delete"),
    path("attachments/<int:attachment_id>/download/", views.download_attachment, name="download_attachment"),
]

