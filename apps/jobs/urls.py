from django.urls import path
from .views import (
    OpenJobListView, JobCreateView, UserApplicationsView,
    JobApplicationsListView, JobApplicationView, JobStatusUpdateView, JobDeleteView,
    JobDetailView, JobFeedbackView, JobPaymentRequestView,
    JobRequestResponseView, JobRequestView, JobUpdateView,
    JobPaymentConfirmView, PaymentCallbackView
)

urlpatterns = [
    path('available/', OpenJobListView.as_view(), name='jobs_available_list'),
    path('create/', JobCreateView.as_view(), name='jobs_create_create'),
    path('my-applications/', UserApplicationsView.as_view(), name='jobs_my-applications_list'),
    path('<int:id>/applications/', JobApplicationsListView.as_view(), name='jobs_applications_list'),
    path('<int:id>/apply/', JobApplicationView.as_view(), name='jobs_apply_create'),
    path('<int:id>/complete/', JobStatusUpdateView.as_view(), name='jobs_complete_update'),
    path('<int:id>/delete/', JobDeleteView.as_view(), name='jobs_delete_delete'),
    path('<int:id>/details/', JobDetailView.as_view(), name='jobs_details_list'),
    path('<int:id>/feedback/', JobFeedbackView.as_view(), name='jobs_feedback_create'),
    path('<int:id>/request-payment/', JobPaymentRequestView.as_view(), name='jobs_request-payment_create'),
    path('<int:id>/request/<int:request_id>/respond/', JobRequestResponseView.as_view(), name='jobs_request_respond_create'),
    path('<int:id>/send-request/', JobRequestView.as_view(), name='jobs_send-request_create'),
    path('<int:id>/update/', JobUpdateView.as_view(), name='jobs_update_update'),
    path('<int:id>/payment-confirm/', JobPaymentConfirmView.as_view(), name='jobs_payment_confirm_create'),
    path('payment-callback/', PaymentCallbackView.as_view(), name='payment_callback'),
]