from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.ManagementUserViewSet)
router.register(r'notification-logs', views.NotificationLogViewSet)
router.register(r'analytics', views.SystemAnalyticsViewSet, basename='analytics')
router.register(r'disputes', views.DisputeManagementViewSet, basename='disputes')
router.register(r'management-logs', views.ManagementLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    
    # User Management
    path('users/search/', views.ManagementUserSearchView.as_view(), name='user-search'),
    path('users/bulk-action/', views.ManagementUserBulkActionView.as_view(), name='user-bulk-action'),
    path('users/<int:user_id>/suspend/', views.ManagementUserSuspendView.as_view(), name='user-suspend'),
    path('users/<int:user_id>/reset-password/', views.ManagementUserResetPasswordView.as_view(), name='user-reset-password'),
    
    # Analytics
    path('analytics/dashboard/', views.AnalyticsDashboardView.as_view(), name='analytics-dashboard'),
    
    # Recommendation Management
    path('recommendations/', views.RecommendationManagementView.as_view(), name='recommendation-management'),
    
    # Notification Management
    path('notifications/templates/', views.NotificationTemplateView.as_view(), name='notification-templates'),
    path('notifications/metrics/', views.NotificationMetricsView.as_view(), name='notification-metrics'),
    path('notifications/broadcast/', views.BroadcastNotificationViewSet.as_view({'post': 'create'}), name='broadcast-notification'),
    
]