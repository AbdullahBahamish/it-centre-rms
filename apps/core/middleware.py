import re
import logging

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.http import HttpResponse, HttpResponseForbidden
from django.urls import reverse

from apps.core.models import SYSTEM_SETTINGS_CACHE_KEY, SystemSettings
from apps.core.security import log_security_event, log_security_failure


logger = logging.getLogger(__name__)


EXEMPT_PATHS = [
    r"^/favicon\.ico$",
    r"^/accounts/login/$",
    r"^/accounts/logout/$",
    r"^/accounts/signup/$",
    r"^/accounts/recover-password/$",
    r"^/accounts/password_reset/$",
    r"^/accounts/password_reset/done/$",
    r"^/accounts/reset/[^/]+/[^/]+/$",
    r"^/accounts/reset/done/$",
    r"^/admin/login/",
    r"^/health/$",
    r"^/api/",
    r"^/static/",
    r"^/i18n/setlang/",
]

PASSWORD_CHANGE_PATH = "/accounts/profile/password/"

AUTHORITY_MUTATION_PATHS = [
    r"^/admin-panel/users/\d+/assign-role/$",
    r"^/admin-panel/users/\d+/activate/$",
    r"^/admin-panel/users/\d+/deactivate/$",
    r"^/admin-panel/password-reset-requests/\d+/approve/$",
    r"^/admin-panel/password-reset-requests/\d+/reject/$",
    r"^/admin-panel/permissions/\d+/$",
]


def is_exempt(path: str) -> bool:
    return any(re.match(pattern, path) for pattern in EXEMPT_PATHS)


class AccessPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            if is_exempt(request.path):
                return self.get_response(request)

            if request.user.is_authenticated:
                profile = getattr(request.user, "userprofile", None)
                if (
                    profile
                    and profile.must_change_password
                    and request.path not in {PASSWORD_CHANGE_PATH, "/accounts/logout/"}
                ):
                    return redirect(PASSWORD_CHANGE_PATH)
                return self.get_response(request)

            system_settings = self._get_system_settings()
            if system_settings is None:
                log_security_event(action="middleware_access_policy", result="denied", reason="policy_unavailable", path=request.path)
                return HttpResponseForbidden(status=settings.ACCESS_DENIED_STATUS_CODE)

            if system_settings["require_login"]:
                login_path = reverse("login")
                if request.path == login_path:
                    log_security_event(action="middleware_access_policy", result="denied", reason="redirect_prevention", path=request.path)
                    return HttpResponseForbidden(status=settings.ACCESS_DENIED_STATUS_CODE)
                return redirect_to_login(request.get_full_path(), login_path)

            if self._is_anonymous_method_allowed(request.method, system_settings):
                return self.get_response(request)

            log_security_event(action="middleware_access_policy", result="denied", reason="anonymous_method_denied", path=request.path, method=request.method)
            return HttpResponseForbidden(status=settings.ACCESS_DENIED_STATUS_CODE)
        except Exception:
            log_security_failure(action="middleware_access_policy", reason="exception", target=request.path)
            return HttpResponseForbidden(status=settings.ACCESS_DENIED_STATUS_CODE)

    @staticmethod
    def _get_system_settings():
        try:
            cached = cache.get(SYSTEM_SETTINGS_CACHE_KEY)
        except Exception:
            cached = None
        if cached is not None:
            return cached

        try:
            system_settings = SystemSettings.get_solo()
        except Exception:
            return None

        policy = {
            "require_login": bool(system_settings.require_login),
            "allow_anonymous_view": bool(system_settings.allow_anonymous_view),
            "allow_anonymous_create": bool(system_settings.allow_anonymous_create),
            "allow_anonymous_update": bool(system_settings.allow_anonymous_update),
            "allow_anonymous_delete": bool(system_settings.allow_anonymous_delete),
        }
        try:
            cache.set(SYSTEM_SETTINGS_CACHE_KEY, policy, timeout=settings.SYSTEM_SETTINGS_CACHE_TTL)
        except Exception:
            pass
        return policy

    @staticmethod
    def _is_anonymous_method_allowed(method, system_settings):
        if method in ("GET", "HEAD", "OPTIONS"):
            return system_settings["allow_anonymous_view"]
        if method == "POST":
            return system_settings["allow_anonymous_create"]
        if method in ("PUT", "PATCH"):
            return system_settings["allow_anonymous_update"]
        if method == "DELETE":
            return system_settings["allow_anonymous_delete"]
        return False


class AuthRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != "POST":
            return self.get_response(request)

        limits = getattr(settings, "AUTH_RATE_LIMITS", {})
        rule = limits.get(request.path)
        if rule:
            limited = self._apply_limit(request, rule, namespace="auth-rate")
            if limited is not None:
                return limited

        if any(re.match(pattern, request.path) for pattern in AUTHORITY_MUTATION_PATHS):
            rule = getattr(settings, "AUTHORITY_MUTATION_RATE_LIMIT", (10, 60))
            limited = self._apply_limit(request, rule, namespace="authority-rate")
            if limited is not None:
                return limited

        return self.get_response(request)

    @staticmethod
    def _rate_limit_key(request, namespace):
        ip = request.META.get("REMOTE_ADDR", "unknown")
        if getattr(request.user, "is_authenticated", False):
            identity = f"user:{request.user.pk}"
        else:
            identity = (
                request.POST.get("username")
                or request.POST.get("email")
                or request.POST.get("identifier")
                or "anonymous"
            )
        return f"{namespace}:{request.path}:{ip}:{identity.lower()}"

    @classmethod
    def _apply_limit(cls, request, rule, namespace):
        limit, window_seconds = rule
        key = cls._rate_limit_key(request, namespace)
        try:
            attempts = cache.get(key, 0)
        except Exception:
            attempts = 0
        if attempts >= limit:
            return HttpResponse(status=429)

        try:
            cache.set(key, attempts + 1, timeout=window_seconds)
        except Exception:
            pass
        return None
