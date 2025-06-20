from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token
from .views import (
    AuthLoginView, AuthSignupInitiateView, AuthSignupRequestCodeView,
    AuthSignupCompleteView, AuthPasswordResetView, AuthPasswordResetConfirmView,
    UserProfileView, UserProfileClientView, UserProfileWorkerView, UserApplicationsView,
    UserRatingStatsView, UserReviewsView, RecentReviewsView, PaymentPreferenceView,
    WorkersByPaymentMethodView, JobsByPaymentMethodView
)

urlpatterns = [
    # Authentication
    path('auth/login/', AuthLoginView.as_view(), name='auth_login'),
    path('auth/signup/initiate/', AuthSignupInitiateView.as_view(), name='auth_signup_initiate'),
    path('auth/signup/request-code/', AuthSignupRequestCodeView.as_view(), name='signup_request_code'),
    path('auth/signup/complete/', AuthSignupCompleteView.as_view(), name='auth_signup_complete'),

    # Password Management
    path('auth/password/reset/', AuthPasswordResetView.as_view(), name='auth_password_reset'),
    path('auth/password/reset/confirm/', AuthPasswordResetConfirmView.as_view(), name='auth_password_reset_confirm'),

    # Profile Management
    path('users/profile/', UserProfileView.as_view(), name='user_profile'),
    path('users/profile/client/', UserProfileClientView.as_view(), name='user_profile_client'),
    path('users/profile/worker/', UserProfileWorkerView.as_view(), name='user_profile_worker'),
    path('users/my-applications/', UserApplicationsView.as_view(), name='user_my_applications'),
    
    # Payment Preferences
    path('users/payment-preference/', PaymentPreferenceView.as_view(), name='payment_preference'),
    path('users/workers/by-payment-method/', WorkersByPaymentMethodView.as_view(), name='workers_by_payment_method'),
    path('users/jobs/by-payment-method/', JobsByPaymentMethodView.as_view(), name='jobs_by_payment_method'),
    
    # Rating Statistics
    path('users/ratings/', UserRatingStatsView.as_view(), name='user_ratings'),
    path('users/<int:user_id>/ratings/', UserRatingStatsView.as_view(), name='user_ratings_by_id'),
    
    # Reviews
    path('users/reviews/', UserReviewsView.as_view(), name='user_reviews'),
    path('users/<int:user_id>/reviews/', UserReviewsView.as_view(), name='user_reviews_by_id'),
    path('users/reviews/recent/', RecentReviewsView.as_view(), name='user_recent_reviews'),
    path('users/<int:user_id>/reviews/recent/', RecentReviewsView.as_view(), name='user_recent_reviews_by_id'),
]