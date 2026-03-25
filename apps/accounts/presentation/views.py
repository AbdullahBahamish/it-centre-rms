from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import INTERNAL_RESET_SESSION_TOKEN, PasswordResetConfirmView
from django.shortcuts import redirect, render
from django.views.generic.edit import FormView

from apps.accounts.application.use_cases import RegisterUserUseCase, RequestPasswordResetUseCase
from apps.accounts.domain.constants import GENERIC_PASSWORD_RESET_MESSAGE
from apps.accounts.presentation.forms import PasswordRecoveryForm, SignupForm


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
            RequestPasswordResetUseCase().execute(
                identifier=form.cleaned_data["identifier"],
                request=request,
            )
            messages.success(request, GENERIC_PASSWORD_RESET_MESSAGE)
            return redirect("recover_password")
    else:
        form = PasswordRecoveryForm()

    return render(request, "registration/password_recover.html", {"form": form})


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
