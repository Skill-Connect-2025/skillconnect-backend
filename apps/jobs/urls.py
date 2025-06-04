from django.urls import path
from .views import (
    JobCreateView, JobListView, JobDetailView, JobUpdateView, JobDeleteView,
    OpenJobListView, JobApplicationView, JobApplicationsListView,
    JobRequestView, JobRequestResponseView, JobStatusUpdateView,
    JobPaymentRequestView, JobFeedbackView, ClientFeedbackView,
    PaymentCallbackView, WorkerJobRequestsView, ClientSentRequestsView, 
    PaymentConfirmView, JobApplicationResponseView, JobReviewsView
)

urlpatterns = [
    path('jobs/create/', JobCreateView.as_view(), name='job_create'),
    path('jobs/', JobListView.as_view(), name='job_list'),
    path('jobs/<int:pk>/details/', JobDetailView.as_view(), name='job_details'), 
    path('jobs/<int:id>/update/', JobUpdateView.as_view(), name='job_update'),
    path('jobs/<int:pk>/delete/', JobDeleteView.as_view(), name='job_delete'),
    path('jobs/open/', OpenJobListView.as_view(), name='open_jobs'),
    path('jobs/<int:id>/apply/', JobApplicationView.as_view(), name='job_apply'),
    path('jobs/<int:id>/applications/', JobApplicationsListView.as_view(), name='job_applications'),
    path('jobs/<int:id>/applications/<int:application_id>/respond/', JobApplicationResponseView.as_view(), name='job_application_response'),
    path('jobs/<int:id>/request/', JobRequestView.as_view(), name='job_request'),
    path('jobs/<int:pk>/requests/<int:request_id>/respond/', JobRequestResponseView.as_view(), name='job_request_response'),
    path('jobs/<int:pk>/status/', JobStatusUpdateView.as_view(), name='job_status_update'),
    path('jobs/<int:pk>/payment-request/', JobPaymentRequestView.as_view(), name='job_payment_request'),
    path('jobs/<int:pk>/feedback/', JobFeedbackView.as_view(), name='job_feedback'),
    path('jobs/<int:pk>/client-feedback/', ClientFeedbackView.as_view(), name='client_feedback'),
    path('jobs/<int:pk>/reviews/', JobReviewsView.as_view(), name='job_reviews'),
    path('payment/callback/', PaymentCallbackView.as_view(), name='payment_callback'),
    path('worker/requests/', WorkerJobRequestsView.as_view(), name='worker_job_requests'), 
    path('client/requests/', ClientSentRequestsView.as_view(), name='client_sent_requests'), 
    path('jobs/<int:id>/payment-confirm/', PaymentConfirmView.as_view(), name='payment-confirm'),
]