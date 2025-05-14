from django.urls import path
from .views import (
    JobCreateView, JobListView, JobDetailView,
    JobUpdateView, JobDeleteView
)

urlpatterns = [
    path('', JobCreateView.as_view(), name='job-create'),
    path('list/', JobListView.as_view(), name='job-list'),
    path('<int:pk>/', JobDetailView.as_view(), name='job-detail'),
    path('<int:pk>/update/', JobUpdateView.as_view(), name='job-update'),
    path('<int:pk>/delete/', JobDeleteView.as_view(), name='job-delete'),
]