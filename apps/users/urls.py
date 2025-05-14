from django.urls import path
from .views import (
    SelectSignupMethodView, SignupRequestView, GetCodeAgainView, VerifyAndCompleteView,
    LoginView, PasswordResetRequestView, PasswordResetConfirmView,
    ClientProfileView, ProfileView
)

urlpatterns = [
    path('signup/select-method/', SelectSignupMethodView.as_view(), name='select-signup-method'),
    path('signup/request/', SignupRequestView.as_view(), name='signup-request'),
    path('signup/get-code-again/', GetCodeAgainView.as_view(), name='get-code-again'),
    path('signup/verify-and-complete/', VerifyAndCompleteView.as_view(), name='verify-and-complete'),
    path('login/', LoginView.as_view(), name='login'),
    path('password/reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password/reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('profile/client/', ClientProfileView.as_view(), name='client-profile'),
    path('profile/', ProfileView.as_view(), name='profile'),
]