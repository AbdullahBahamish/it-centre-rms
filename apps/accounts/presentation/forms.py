from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from apps.accounts.infrastructure.repositories import UserProfileRepository

User = get_user_model()


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Email")
    phone_number = forms.CharField(required=True, max_length=30, label="Phone Number")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "password1", "password2")

    def clean_phone_number(self):
        phone_number = self.cleaned_data["phone_number"].strip()
        if UserProfileRepository().phone_exists(phone_number=phone_number):
            raise forms.ValidationError("This phone number is already used by another account.")
        return phone_number


class PasswordRecoveryForm(forms.Form):
    identifier = forms.CharField(
        label="Email or Phone Number",
        max_length=100,
        help_text="Enter the email address or phone number linked to your account.",
    )
