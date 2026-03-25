from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm

from apps.accounts.infrastructure.repositories import UserProfileRepository, UserRepository


class RegisterUserUseCase:
    def __init__(self, user_repo=None, profile_repo=None):
        self.user_repo = user_repo or UserRepository()
        self.profile_repo = profile_repo or UserProfileRepository()

    def execute(self, *, username: str, email: str, password: str, phone_number: str):
        user = self.user_repo.create_user(username=username, email=email, password=password)
        self.profile_repo.ensure_profile(
            user=user,
            phone_number=phone_number,
        )
        return user


class RequestPasswordResetUseCase:
    def __init__(self, user_repo=None):
        self.user_repo = user_repo or UserRepository()

    def execute(self, *, identifier: str, request):
        emails = self.user_repo.find_emails_by_identifier(identifier=identifier.strip())
        for email in emails:
            form = PasswordResetForm({"email": email})
            if form.is_valid():
                form.save(
                    request=request,
                    email_template_name="registration/password_reset_email.txt",
                    subject_template_name="registration/password_reset_subject.txt",
                    domain_override=settings.ALLOWED_HOSTS[0],
                    use_https=request.is_secure(),
                )
