from django.contrib.auth import get_user_model

from apps.accounts.bootstrap import ensure_user_profile
from apps.accounts.domain.constants import DEFAULT_USER_ROLE
from apps.accounts.models import Role, UserProfile

User = get_user_model()


class UserRepository:
    @staticmethod
    def create_user(*, username: str, email: str, password: str):
        return User.objects.create_user(username=username, email=email, password=password)

    @staticmethod
    def find_emails_by_identifier(identifier: str):
        if "@" in identifier:
            queryset = User.objects.filter(email__iexact=identifier).exclude(email="")
        else:
            queryset = User.objects.filter(userprofile__phone_number=identifier).exclude(email="")
        return list(queryset.values_list("email", flat=True).distinct())


class RoleRepository:
    @staticmethod
    def get_by_name(name: str):
        return Role.objects.filter(name=name).first()

    @staticmethod
    def get_default_role():
        return RoleRepository.get_by_name(DEFAULT_USER_ROLE)

    @staticmethod
    def all_roles():
        return Role.objects.all().order_by("-name")


class UserProfileRepository:
    @staticmethod
    def create_profile(*, user, phone_number: str):
        return ensure_user_profile(user=user, phone_number=phone_number)

    @staticmethod
    def ensure_profile(*, user, phone_number=None):
        return ensure_user_profile(user=user, phone_number=phone_number)

    @staticmethod
    def phone_exists(phone_number: str):
        return UserProfile.objects.filter(phone_number=phone_number).exists()
