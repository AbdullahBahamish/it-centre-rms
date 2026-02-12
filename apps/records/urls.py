from django.urls import path
from . import views

urlpatterns = [
    path("", views.record_list, name="record_list"),
    path("create/", views.record_create, name="record_create"),
    path("<int:record_id>/", views.record_detail, name="record_detail"),
    path("<int:record_id>/upload/", views.upload_attachment, name="upload_attachment"),
]
