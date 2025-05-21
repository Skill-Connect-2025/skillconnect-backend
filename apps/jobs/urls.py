from django.urls import path
from .views import (
    JobCreateView, JobListView, JobDetailView, JobUpdateView, JobDeleteView,
    OpenJobListView, JobApplicationView, JobApplicationsListView,
    JobRequestView, JobRequestResponseView, JobStatusUpdateView,
    JobPaymentRequestView, JobFeedbackView, UserApplicationsView
)

urlpatterns = [
    # Job Creation and Listing
    path('create/', JobCreateView.as_view(), name='job_create'),
    path('my-jobs/', JobListView.as_view(), name='job_list'),
    path('available/', OpenJobListView.as_view(), name='job_available'),
    path('<int:pk>/details/', JobDetailView.as_view(), name='job_detail'),

    # Job Applications
    path('<int:pk>/applications/', JobApplicationsListView.as_view(), name='job_applications'),
    path('<int:pk>/apply/', JobApplicationView.as_view(), name='job_apply'),
    path('my-applications/', UserApplicationsView.as_view(), name='job_my_applications'),

    # Job Management
    path('<int:pk>/update/', JobUpdateView.as_view(), name='job_update'),
    path('<int:pk>/delete/', JobDeleteView.as_view(), name='job_delete'),

    # Job Status and Feedback
    path('<int:pk>/complete/', JobStatusUpdateView.as_view(), name='job_complete'),
    path('<int:pk>/feedback/', JobFeedbackView.as_view(), name='job_feedback'),

    # Job Requests and Payments
    path('<int:pk>/send-request/', JobRequestView.as_view(), name='job_send_request'),
    path('<int:pk>/request/<int:request_id>/respond/', JobRequestResponseView.as_view(), name='job_request_respond'),
    path('<int:pk>/request-payment/', JobPaymentRequestView.as_view(), name='job_request_payment'),
]