# apps/records/admin.py

from django.contrib import admin
from .models import Category, ITAsset, Record, RecordType


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = ("title", "asset", "maintenance_type", "priority", "maintenance_status", "assigned_technician", "created_at")
    list_filter = ("maintenance_status", "priority", "maintenance_type", "record_type", "category")
    search_fields = ("title", "asset__asset_tag", "asset__serial_number", "category__name")
    filter_horizontal = ("contributors",)


@admin.register(ITAsset)
class ITAssetAdmin(admin.ModelAdmin):
    list_display = ("asset_tag", "device_type", "manufacturer", "model", "serial_number", "department", "room")
    list_filter = ("device_type", "manufacturer", "operating_system", "system_architecture")
    search_fields = ("asset_tag", "serial_number", "model", "device_owner", "department", "room")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")
    search_fields = ("name",)
    filter_horizontal = ("allowed_users",)


@admin.register(RecordType)
class RecordTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)
