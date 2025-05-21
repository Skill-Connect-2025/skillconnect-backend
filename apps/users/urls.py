from django.urls import path
from .views import (
    AuthLoginView, AuthSignupInitiateView, AuthSignupVerifyView,
    AuthSignupResendCodeView, AuthSignupCompleteView, AuthPasswordResetView,
    AuthPasswordResetConfirmView, UserProfileView, UserProfileClientView,
    UserProfileWorkerView, UserApplicationsView
)

urlpatterns = [
    # Authentication
    path('auth/login/', AuthLoginView.as_view(), name='auth_login'),
    path('auth/signup/initiate/', AuthSignupInitiateView.as_view(), name='auth_signup_initiate'),
    path('auth/signup/verify/', AuthSignupVerifyView.as_view(), name='auth_signup_verify'),
    path('auth/signup/resend-code/', AuthSignupResendCodeView.as_view(), name='auth_signup_resend_code'),
    path('auth/signup/complete/', AuthSignupCompleteView.as_view(), name='auth_signup_complete'),

    # Password Management
    path('auth/password/reset/', AuthPasswordResetView.as_view(), name='auth_password_reset'),
    path('auth/password/reset/confirm/', AuthPasswordResetConfirmView.as_view(), name='auth_password_reset_confirm'),

    # Profile Management
    path('users/profile/', UserProfileView.as_view(), name='user_profile'),
    path('users/profile/client/', UserProfileClientView.as_view(), name='user_profile_client'),
    path('users/profile/worker/', UserProfileWorkerView.as_view(), name='user_profile_worker'),
    path('users/my-applications/', UserApplicationsView.as_view(), name='user_my_applications'),
]