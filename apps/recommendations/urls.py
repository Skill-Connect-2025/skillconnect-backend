from django.urls import path
from . import views

urlpatterns = [
    path('jobs/<int:job_id>/workers/', views.JobWorkerRecommendationView.as_view(), name='job-worker-recommendations'),
    path('workers/me/jobs/', views.WorkerJobRecommendationView.as_view(), name='worker-job-recommendations'),
]