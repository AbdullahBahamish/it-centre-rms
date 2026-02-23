from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from .models import UserProfile

User = get_user_model()


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True, label=_("Email"))
    phone_number = forms.CharField(
        required=True,
        max_length=30,
        label=_("Phone Number"),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_phone_number(self):
        phone_number = self.cleaned_data["phone_number"].strip()
        if UserProfile.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError(_("This phone number is already used by another account."))
        return phone_number


class PasswordRecoveryForm(forms.Form):
    identifier = forms.CharField(
        label=_("Email or Phone Number"),
        max_length=100,
        help_text=_("Enter the email address or phone number linked to your account."),
    )
