# apps/records/admin.py

from django.contrib import admin
from .models import Category, Record


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = ("title", "record_type", "category", "status", "created_at")
    list_filter = ("status", "record_type", "category")
    search_fields = ("title", "category__name")
    filter_horizontal = ("contributors",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "created_by", "created_at")
    search_fields = ("name",)
    filter_horizontal = ("allowed_users",)
