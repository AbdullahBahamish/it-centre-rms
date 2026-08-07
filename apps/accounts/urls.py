from django.urls import path

from apps.accounts.presentation import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("recover-password/", views.recover_password, name="recover_password"),
    path("profile/", views.profile, name="profile"),
    path("profile/password/", views.change_password, name="change_password"),
    path("profile/picture/", views.profile_picture, name="profile_picture"),
    path("profile/picture/remove/", views.remove_profile_picture, name="remove_profile_picture"),
    path(
        "reset/<uidb64>/<token>/",
        views.IntranetPasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
]
