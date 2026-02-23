from django.urls import path
from . import views

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("recover-password/", views.recover_password, name="recover_password"),
]
