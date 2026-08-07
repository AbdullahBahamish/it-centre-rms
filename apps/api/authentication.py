from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class ExpiringTokenAuthentication(TokenAuthentication):
    def authenticate_credentials(self, key):
        user, token = super().authenticate_credentials(key)
        ttl = timedelta(seconds=settings.API_TOKEN_TTL_SECONDS)
        if token.created + ttl <= timezone.now():
            token.delete()
            raise AuthenticationFailed("API token has expired.")
        return user, token
