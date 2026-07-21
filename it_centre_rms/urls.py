from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.templatetags.static import static as static_url
from django.urls import include, path


def home(request):
    return redirect("record_list")


def favicon(request):
    return redirect(static_url("images/favicon.ico"))


urlpatterns = [
    path("", home),
    path("favicon.ico", favicon),
    path("", include("apps.core.urls")),
    path("admin/", admin.site.urls),
    path("records/", include("apps.records.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/password_reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("accounts/password_reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]

if settings.DEBUG:
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
else:
    from django.conf.urls.static import static as static_serve
    from django.views.static import serve
    from django.urls import re_path

    urlpatterns += static_serve(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", serve, {"document_root": settings.STATIC_ROOT}),
    ]
