from django.contrib.auth import login, get_user_model
from django.shortcuts import render, redirect
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from .forms import PasswordRecoveryForm, SignupForm
from .models import UserProfile

User = get_user_model()


def signup(request):
    """Handle user signup/registration"""
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.email = form.cleaned_data["email"]
            user.save(update_fields=["email"])

            UserProfile.objects.create(
                user=user,
                phone_number=form.cleaned_data["phone_number"],
            )

            login(request, user)  # Auto-login after signup
            return redirect("record_list")
    else:
        form = SignupForm()
    
    return render(request, "registration/signup.html", {
        "form": form
    })


def recover_password(request):
    temporary_password = None

    if request.method == "POST":
        form = PasswordRecoveryForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data["identifier"].strip()
            user = _find_user_by_identifier(identifier)

            if user is None:
                form.add_error("identifier", _("No account matches this email or phone number."))
            else:
                temporary_password = get_random_string(10)
                user.set_password(temporary_password)
                user.save(update_fields=["password"])
    else:
        form = PasswordRecoveryForm()

    return render(
        request,
        "registration/password_recover.html",
        {
            "form": form,
            "temporary_password": temporary_password,
        },
    )


def _find_user_by_identifier(identifier: str):
    if "@" in identifier:
        users = User.objects.filter(email__iexact=identifier)
    else:
        users = User.objects.filter(profile__phone_number=identifier)

    if users.count() != 1:
        return None

    return users.first()
