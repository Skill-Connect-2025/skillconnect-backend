from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from apps.jobs.views import AdminDisputeListView, AdminDisputeResolveView
from .views import RecommendedWorkersForJobView, RecommendedJobsForWorkerView

router = DefaultRouter()
router.register(r'users', views.ManagementUserViewSet)
router.register(r'analytics', views.SystemAnalyticsViewSet, basename='analytics')
router.register(r'disputes', views.DisputeManagementViewSet, basename='disputes')
router.register(r'management-logs', views.ManagementLogViewSet)
router.register(r'categories', views.CategoryViewSet, basename='categories')
router.register(r'jobs', views.JobViewSet, basename='jobs')

urlpatterns = [
    path('', include(router.urls)),
    
    # Recommendation Management
    path('recommendations/job/<int:job_id>/workers/', RecommendedWorkersForJobView.as_view(), name='recommended-workers-for-job'),
    path('recommendations/worker/<int:worker_id>/jobs/', RecommendedJobsForWorkerView.as_view(), name='recommended-jobs-for-worker'),
    path('recommendations/', views.RecommendationManagementView.as_view(), name='recommendation-management'),
    
    # Admin Dispute URLs
    path('admin/disputes/', AdminDisputeListView.as_view(), name='admin_list_disputes'),
    path('admin/disputes/<int:dispute_id>/resolve/', AdminDisputeResolveView.as_view(), name='admin_resolve_dispute'),
    
]