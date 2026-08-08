from django.contrib import messages
from django.conf import settings
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import FileResponse, Http404
from django.contrib.auth.views import INTERNAL_RESET_SESSION_TOKEN, PasswordResetConfirmView
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.generic.edit import FormView

from apps.accounts.application.use_cases import RegisterUserUseCase, RequestPasswordResetUseCase
from apps.accounts.domain.constants import GENERIC_PASSWORD_RESET_MESSAGE
from apps.accounts.models import PasswordResetRequest
from apps.accounts.presentation.forms import PasswordRecoveryForm, ProfileUpdateForm, SignupForm


def signup(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = RegisterUserUseCase().execute(
                username=form.cleaned_data["username"],
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password1"],
                phone_number=form.cleaned_data["phone_number"],
            )
            login(request, user)
            return redirect("record_list")
    else:
        form = SignupForm()

    return render(request, "registration/signup.html", {"form": form})


def recover_password(request):
    if request.method == "POST":
        form = PasswordRecoveryForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data["identifier"].strip()
            if settings.PASSWORD_RESET_METHOD == "email":
                RequestPasswordResetUseCase().execute(identifier=identifier, request=request)
            else:
                user = get_user_model().objects.filter(
                    Q(username__iexact=identifier)
                    | Q(email__iexact=identifier)
                    | Q(userprofile__phone_number=identifier)
                ).first()
                PasswordResetRequest.objects.create(identifier=identifier, user=user)
            messages.success(request, GENERIC_PASSWORD_RESET_MESSAGE)
            return redirect("recover_password")
    else:
        form = PasswordRecoveryForm()

    return render(request, "registration/password_recover.html", {"form": form})


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            request.user.email = form.cleaned_data["email"]
            request.user.save(update_fields=["email"])
            user_profile = request.user.userprofile
            user_profile.phone_number = form.cleaned_data["phone_number"]
            if form.cleaned_data.get("profile_picture"):
                user_profile.profile_picture = form.cleaned_data["profile_picture"]
            user_profile.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("profile")
    else:
        form = ProfileUpdateForm(user=request.user)
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def change_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            user.userprofile.must_change_password = False
            user.userprofile.save(update_fields=["must_change_password"])
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been changed.")
            return redirect("profile")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "accounts/change_password.html", {"form": form})


@login_required
def profile_picture(request):
    file_field = request.user.userprofile.profile_picture
    if not file_field or not file_field.name or not file_field.storage.exists(file_field.name):
        raise Http404
    return FileResponse(file_field.open("rb"), content_type="image/*")


@login_required
def remove_profile_picture(request):
    if request.method != "POST":
        return redirect("profile")
    user_profile = request.user.userprofile
    if user_profile.profile_picture:
        user_profile.profile_picture.delete(save=False)
        user_profile.profile_picture = ""
        user_profile.save(update_fields=["profile_picture"])
    messages.success(request, "Your profile picture has been removed.")
    return redirect("profile")


class IntranetPasswordResetConfirmView(PasswordResetConfirmView):
    def dispatch(self, *args, **kwargs):
        self.validlink = False
        self.user = self.get_user(kwargs["uidb64"])

        if self.user is not None:
            token = kwargs["token"]
            session_token = self.request.session.get(INTERNAL_RESET_SESSION_TOKEN)
            effective_token = session_token if token == self.reset_url_token else token

            if effective_token and self.token_generator.check_token(self.user, effective_token):
                self.request.session[INTERNAL_RESET_SESSION_TOKEN] = effective_token
                self.validlink = True
                kwargs["token"] = self.reset_url_token
                return FormView.dispatch(self, *args, **kwargs)

        return self.render_to_response(self.get_context_data())
