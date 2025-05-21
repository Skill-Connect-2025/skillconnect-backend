from django.urls import path
from .views import (
    JobCreateView, JobListView, JobDetailView, JobUpdateView, JobDeleteView,
    OpenJobListView, JobApplicationView, JobApplicationsListView,
    JobRequestView, JobRequestResponseView, JobStatusUpdateView,
    JobPaymentRequestView, JobFeedbackView
)

urlpatterns = [
    path('', JobCreateView.as_view(), name='job-create'),
    path('list/', JobListView.as_view(), name='job-list'),
    path('<int:pk>/', JobDetailView.as_view(), name='job-detail'),
    path('<int:pk>/update/', JobUpdateView.as_view(), name='job-update'),
    path('<int:pk>/delete/', JobDeleteView.as_view(), name='job-delete'),
    path('open/', OpenJobListView.as_view(), name='open-jobs'),
    path('<int:pk>/apply/', JobApplicationView.as_view(), name='job-apply'),
    path('<int:pk>/applications/', JobApplicationsListView.as_view(), name='job-applications'),
    path('<int:pk>/request/', JobRequestView.as_view(), name='job-request'),
    path('<int:pk>/request/<int:request_id>/respond/', JobRequestResponseView.as_view(), name='job-request-respond'),
    path('<int:pk>/status/', JobStatusUpdateView.as_view(), name='job-status'),
    path('<int:pk>/payment/request/', JobPaymentRequestView.as_view(), name='job-payment-request'),
    path('<int:pk>/feedback/', JobFeedbackView.as_view(), name='job-feedback'),
]