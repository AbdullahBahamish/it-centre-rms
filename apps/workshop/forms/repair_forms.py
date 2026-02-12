from django import forms
from django.contrib.auth import get_user_model
from apps.workshop.models.repair_case import RepairCase

User = get_user_model()


class PublicRepairCaseForm(forms.ModelForm):

    technicians = forms.ModelMultipleChoiceField(
        queryset=User.objects.all().order_by("username"),
        widget=forms.CheckboxSelectMultiple,
        help_text="Select all technicians who worked on this case"
    )

    class Meta:
        model = RepairCase
        fields = [
            "technicians",
            "category",
            "serial_number",
            "device_type",
            "brand_model",
            "problem_description",
            "actions_taken",
            "final_status",
        ]
