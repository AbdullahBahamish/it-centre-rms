from django.urls import include, path

from apps.core.views import health_check


urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("admin-panel/", include("apps.core.admin_panel.urls")),
]
