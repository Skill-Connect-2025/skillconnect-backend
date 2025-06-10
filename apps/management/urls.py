from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.ManagementUserViewSet)
router.register(r'notifications', views.NotificationLogViewSet, basename='notification')
router.register(r'analytics', views.SystemAnalyticsViewSet, basename='analytics')
router.register(r'logs', views.ManagementLogViewSet, basename='log')
router.register(r'disputes', views.DisputeManagementViewSet, basename='dispute')

urlpatterns = [
    path('', include(router.urls)),
    path('broadcast/', views.BroadcastNotificationViewSet.as_view({'post': 'create'}), name='broadcast-notification'),
    path('users/<int:pk>/reset-password/', views.ManagementUserResetPasswordView.as_view(), name='user-reset-password'),
]