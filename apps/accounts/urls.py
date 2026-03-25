from django.urls import path

from apps.accounts.presentation import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("recover-password/", views.recover_password, name="recover_password"),
    path(
        "reset/<uidb64>/<token>/",
        views.IntranetPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]
