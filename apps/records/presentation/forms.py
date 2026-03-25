from django import forms
from django.contrib.auth import get_user_model

from apps.records.models import Category

User = get_user_model()


class RecordForm(forms.Form):
    title = forms.CharField(max_length=255, label="Title")
    record_type = forms.CharField(max_length=100, label="Record Type")
    category = forms.ModelChoiceField(queryset=Category.objects.none(), label="Category")
    retention_until = forms.DateField(required=False, label="Retention Until")
    contributors = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Contributors",
        help_text="Hold Ctrl (Windows) or Command (Mac) to select more than one user.",
        widget=forms.SelectMultiple(
            attrs={
                "class": "form-control",
                "size": 6,
            }
        ),
    )
    case_description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        required=False,
        label="Description",
    )

    def __init__(self, *args, categories=None, users=None, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(categories, list):
            categories = Category.objects.filter(id__in=[category.id for category in categories])
        if isinstance(users, list):
            users = User.objects.filter(id__in=[user.id for user in users])
        self.fields["category"].queryset = categories if categories is not None else Category.objects.none()
        self.fields["contributors"].queryset = users if users is not None else User.objects.none()


class AttachmentUploadForm(forms.Form):
    file = forms.FileField()
