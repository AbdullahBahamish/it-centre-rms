from django.core.management.base import BaseCommand

from apps.records.models import Category, RecordType


CATEGORIES = (
    "Hardware Maintenance",
    "Software Support",
    "Network and Connectivity",
    "Account and Access",
    "Security Incident",
    "Printing and Scanning",
    "Email and Communication",
    "Backup and Recovery",
    "System Performance",
    "Asset Replacement",
    "New Equipment Setup",
    "Preventive Maintenance",
)

RECORD_TYPES = (
    "Maintenance Request",
    "Incident Report",
    "Service Request",
    "Preventive Maintenance",
    "Equipment Installation",
    "Equipment Replacement",
    "Access Request",
    "Security Incident",
    "Network Outage",
    "Software Installation",
)


class Command(BaseCommand):
    help = "Create the standard RMS categories and record types without duplicates."

    def handle(self, *args, **options):
        created_categories = sum(Category.objects.get_or_create(name=name)[1] for name in CATEGORIES)
        created_record_types = sum(RecordType.objects.get_or_create(name=name)[1] for name in RECORD_TYPES)
        self.stdout.write(self.style.SUCCESS(
            f"Reference data ready: {created_categories} categories and {created_record_types} record types created."
        ))
