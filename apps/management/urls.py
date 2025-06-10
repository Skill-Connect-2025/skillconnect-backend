from django.urls import path
from .views import (
    ManagementUserListView, ManagementUserDetailView, ManagementUserSuspendView,
    ManagementUserResetPasswordView
)

urlpatterns = [
    path('users/', ManagementUserListView.as_view(), name='management_user_list'),
    path('users/<int:user_id>/', ManagementUserDetailView.as_view(), name='management_user_detail'),
    path('users/<int:user_id>/suspend/', ManagementUserSuspendView.as_view(), name='management_user_suspend'),
    path('users/<int:user_id>/reset-password/', ManagementUserResetPasswordView.as_view(), name='management_user_reset_password'),
]