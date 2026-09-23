from django.urls import path

from . import views

urlpatterns = [
    path("auth/register", views.RegisterView.as_view(), name="auth-register"),
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
    path("auth/refresh", views.RefreshView.as_view(), name="auth-refresh"),
    path("auth/logout", views.LogoutView.as_view(), name="auth-logout"),
    path(
        "auth/firebase/exchange",
        views.FirebaseExchangeView.as_view(),
        name="auth-firebase-exchange",
    ),
    path(
        "auth/password-reset/request",
        views.PasswordResetRequestView.as_view(),
        name="auth-password-reset-request",
    ),
    path(
        "auth/password-reset/confirm",
        views.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path(
        "auth/email-verification/request",
        views.EmailVerificationRequestView.as_view(),
        name="auth-email-verification-request",
    ),
    path(
        "auth/email-verification/confirm",
        views.EmailVerificationConfirmView.as_view(),
        name="auth-email-verification-confirm",
    ),
    path("me", views.MeView.as_view(), name="me"),
]
