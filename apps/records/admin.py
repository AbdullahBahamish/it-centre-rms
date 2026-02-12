# apps/records/admin.py

from django.contrib import admin
from .models import Record


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = ("title", "record_type", "status", "created_at")
    list_filter = ("status", "record_type")
    search_fields = ("title",)
