from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from PIL import Image, UnidentifiedImageError

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


class ProfileUpdateForm(forms.Form):
    email = forms.EmailField(required=True, label="Email")
    phone_number = forms.CharField(required=True, max_length=30, label="Phone Number")
    profile_picture = forms.FileField(required=False, label="Profile Picture")

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["email"].initial = user.email
        generated_phone = f"user-{user.pk}"
        self.fields["phone_number"].initial = "" if user.userprofile.phone_number == generated_phone else user.userprofile.phone_number
        self.fields["phone_number"].help_text = "Enter your real contact number."

    def clean_email(self):
        email = self.cleaned_data["email"].strip()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("This email address is already used by another account.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data["phone_number"].strip()
        if UserProfileRepository().phone_exists(phone_number=phone_number) and phone_number != self.user.userprofile.phone_number:
            raise forms.ValidationError("This phone number is already used by another account.")
        return phone_number

    def clean_profile_picture(self):
        picture = self.cleaned_data.get("profile_picture")
        if picture and picture.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Profile pictures must be 5 MB or smaller.")
        if picture:
            try:
                image = Image.open(picture)
                image.verify()
                picture.seek(0)
            except (UnidentifiedImageError, OSError):
                raise forms.ValidationError("Upload a valid image file.")
        return picture
