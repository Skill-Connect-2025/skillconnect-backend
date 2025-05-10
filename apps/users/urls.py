from django.urls import path

from .views import RegisterView, LoginView, ProfileView, ProfileUpdateView, CompleteProfileView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('profile/update/', ProfileUpdateView.as_view(), name='profile-update'),
    path('complete-profile/', CompleteProfileView.as_view(), name='complete-profile'),
]