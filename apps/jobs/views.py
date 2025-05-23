from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Job, JobApplication, JobRequest, Feedback, PaymentRequest, Payment, JobImage, Category
from .serializers import (
    JobSerializer, JobApplicationSerializer, JobRequestSerializer,
    PaymentRequestSerializer, FeedbackSerializer, JobRequestResponseSerializer,
    JobStatusUpdateSerializer, PaymentConfirmSerializer,
)
from core.utils import IsClient, IsWorker
from django.core.mail import send_mail
from django.conf import settings
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient
from django.contrib.auth import get_user_model
import logging
import hmac
import hashlib
import requests
import re 

User = get_user_model()

logger = logging.getLogger(__name__)

def send_notification(user, subject, email_message, sms_message):
    """Send notification via email and SMS (if phone_number is valid)."""
    # Send email
    try:
        send_mail(
            subject=subject,
            message=email_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Failed to send email to {user.email}: {str(e)}")

    # Send SMS if phone_number exists and is valid
    if user.phone_number:
        # Validate phone number format (e.g., starts with + followed by 9-15 digits)
        if not re.match(r'^\+\d{9,15}$', user.phone_number):
            logger.warning(f"Invalid phone number format for user {user.id}: {user.phone_number}")
            # Fallback to email without mentioning failure
            try:
                send_mail(
                    subject=subject,
                    message=email_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Failed to send fallback email to {user.email}: {str(e)}")
            return
        try:
            twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            twilio_client.messages.create(
                body=sms_message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=user.phone_number
            )
        except TwilioRestException as e:
            logger.error(f"Failed to send SMS to {user.phone_number}: {str(e)}")
            # Fallback to email without mentioning failure
            try:
                send_mail(
                    subject=subject,
                    message=email_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Failed to send fallback email to {user.email}: {str(e)}")


class JobCreateView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Create a new job. Photos are optional.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['title', 'location', 'skills', 'description', 'category_id', 'payment_method'],
            properties={
                'title': openapi.Schema(type=openapi.TYPE_STRING),
                'location': openapi.Schema(type=openapi.TYPE_STRING),
                'skills': openapi.Schema(type=openapi.TYPE_STRING),
                'description': openapi.Schema(type=openapi.TYPE_STRING),
                'category_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'payment_method': openapi.Schema(type=openapi.TYPE_STRING, enum=['telebirr', 'chapa', 'e_birr', 'cash']),
                'uploaded_images': openapi.Schema(type=openapi.TYPE_FILE, nullable=True),
            },
        ),
        consumes=['multipart/form-data'],
        responses={
            201: JobSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def post(self, request):
        serializer = JobSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(client=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class JobListView(APIView):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="List all jobs posted by the authenticated client.",
        responses={200: JobSerializer(many=True), 401: 'Unauthorized', 403: 'Forbidden'}
    )
    def get(self, request):  # Fixed: Added get method
        queryset = Job.objects.filter(client=self.request.user)
        serializer = JobSerializer(queryset, many=True)
        return Response(serializer.data)

class JobDetailView(generics.RetrieveAPIView):  # Fixed: Changed to RetrieveAPIView
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsClient]

    def get_object(self):  # Fixed: Added get_object method
        job = super().get_object()
        if job.client != self.request.user:
            self.permission_denied(self.request, message="Not authorized to view this job")
        return job

    @swagger_auto_schema(
        operation_description="Retrieve details of a specific job (client must own the job).",
        responses={200: JobSerializer, 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found'}
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class JobUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Update a job. Photos are optional.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'title': openapi.Schema(type=openapi.TYPE_STRING),
                'location': openapi.Schema(type=openapi.TYPE_STRING),
                'skills': openapi.Schema(type=openapi.TYPE_STRING),
                'description': openapi.Schema(type=openapi.TYPE_STRING),
                'category_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'payment_method': openapi.Schema(type=openapi.TYPE_STRING, enum=['telebirr', 'chapa', 'e_birr', 'cash']),
                'uploaded_images': openapi.Schema(type=openapi.TYPE_FILE, nullable=True),
            },
        ),
        consumes=['multipart/form-data'],
        responses={
            200: JobSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def put(self, request, id):  # Fixed: Changed parameter from pk to id
        try:
            job = Job.objects.get(pk=id, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        serializer = JobSerializer(job, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class JobDeleteView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Delete a job.",
        responses={
            204: 'No Content',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def delete(self, request, pk):
        try:
            job = Job.objects.get(pk=pk, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class OpenJobListView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="List all open jobs for workers.",
        responses={200: JobSerializer(many=True), 401: 'Unauthorized', 403: 'Forbidden'}
    )
    def get(self, request):
        jobs = Job.objects.filter(status='open')
        serializer = JobSerializer(jobs, many=True)
        return Response(serializer.data)

class JobApplicationView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="Apply to an open job.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'worker_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='Worker ID (ignored, auto-set to current user)'
                )
            }
        ),
        responses={
            201: JobApplicationSerializer,
            400: openapi.Response('Bad Request', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={'error': openapi.Schema(type=openapi.TYPE_STRING)}
            )),
            401: openapi.Response('Unauthorized'),
            403: openapi.Response('Forbidden'),
            404: openapi.Response('Not Found')
        }
    )
    def post(self, request, id):  # Fixed: Changed parameter from id to id (already correct)
        try:
            job = Job.objects.get(pk=id)
        except Job.DoesNotExist:
            logger.error(f"Job {id} not found for application")
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
        
        data = {
            'job': job.id,
            'worker_id': request.user.worker.id
        }
        
        serializer = JobApplicationSerializer(
            data=data,
            context={'request': request, 'job': job}
        )
        
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Worker {request.user.worker.id} applied to job {id}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        logger.error(f"Job application failed for job {id}: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class JobApplicationsListView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="List all applications for a job (client must own the job).",
        responses={
            200: JobApplicationSerializer(many=True),
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def get(self, request, id):
        try:
            job = Job.objects.get(pk=id, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        applications = job.applications.all()
        serializer = JobApplicationSerializer(applications, many=True)
        return Response(serializer.data)



class UserApplicationsView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]  # Fixed: Changed to IsWorker

    @swagger_auto_schema(
        operation_description="List all applications submitted by the authenticated worker.",
        responses={
            200: JobApplicationSerializer(many=True),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):  # Fixed: Removed pk parameter
        applications = JobApplication.objects.filter(worker=request.user.worker)
        serializer = JobApplicationSerializer(applications, many=True)
        return Response(serializer.data)

class JobPaymentConfirmView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Confirm payment for a job in pending_payment status using Chapa (test mode) or cash.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER, description='Payment amount (required for non-cash, optional for cash)', nullable=True),
            },
        ),
        responses={
            201: PaymentConfirmSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, id):
        try:
            job = Job.objects.get(id=id, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)

        if job.payment_method == 'cash':
            data = request.data.copy()
            data['job'] = job.id
            data['client'] = request.user.id
            data['worker'] = job.assigned_worker.id
            data['payment_method'] = job.payment_method
            serializer = PaymentConfirmSerializer(data=data, context={'request': request})
            if serializer.is_valid():
                payment = serializer.save(status='completed')
                job.status = 'paid'
                job.save()
                self.send_notifications(job, payment)
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = request.data.copy()
        data['job'] = job.id
        data['client'] = request.user.id
        data['worker'] = job.assigned_worker.id
        data['payment_method'] = job.payment_method
        serializer = PaymentConfirmSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            payment = serializer.save(status='pending')
            chapa_response = self.initialize_chapa_payment(payment, request.user)
            if chapa_response['status']:
                payment.transaction_id = chapa_response['data'].get('id')
                payment.save()
                return Response({
                    'payment': serializer.data,
                    'checkout_url': chapa_response['data']['checkout_url']
                }, status=status.HTTP_201_CREATED)
            else:
                payment.delete()
                return Response({"error": chapa_response['message']}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def initialize_chapa_payment(self, payment, user):
        job = payment.job
        body = {
            'amount': str(payment.amount),
            'currency': 'ETB',
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name or '',
            'phone_number': user.phone_number or '0912345678',  # Fallback number
            'tx_ref': payment.tx_ref,
            'callback_url': settings.CHAPA_CALLBACK_URL,
            'return_url': settings.CHAPA_RETURN_URL,
            'customization[title]': f"Payment for Job: {job.title}",
            'customization[description]': f"Payment to {job.assigned_worker.user.first_name} for job ID {job.id}"
        }
        headers = {
            'Authorization': f'Bearer {settings.CHAPA_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.post(settings.CHAPA_PAYMENT_ENDPOINT, json=body, headers=headers)
            response.raise_for_status()
            data = response.json()
            if data.get('status') == 'success':
                return {'status': True, 'data': data['data']}
            return {'status': False, 'message': data.get('message', 'Chapa transaction failed')}
        except requests.RequestException as e:
            logger.error(f"Chapa initialization failed: {str(e)}")
            return {'status': False, 'message': str(e)}

    def send_notifications(self, job, payment):
        status_message = "confirmed" if payment.status == 'completed' else "failed"
        email_subject = f"Payment {status_message.capitalize()} for Job: {job.title}"
        email_message = (
            f"Dear {job.assigned_worker.user.first_name},\n\n"
            f"Client {job.client.first_name} has {status_message} payment for job: {job.title}.\n"
            f"Payment Method: {payment.payment_method}\n"
            f"Amount: {payment.amount or 'Not specified'}\n"
            f"Transaction ID: {payment.transaction_id or 'Not applicable'}\n"
            f"Status: {payment.status}\n\n"
            f"Best regards,\nSkillConnect Team"
        )
        sms_message = f"Payment {status_message} for job: {job.title}. Method: {payment.payment_method}. Status: {payment.status}."
        send_notification(job.assigned_worker.user, email_subject, email_message, sms_message)

class PaymentCallbackView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        operation_description="Handle Chapa webhook for payment verification in test mode, including failed payments.",
        responses={
            200: 'Payment verified',
            400: 'Verification failed',
            401: 'Invalid webhook signature'
        }
    )
    def post(self, request):
        signature = request.headers.get('Chapa-Webhook-Signature')
        if not self.verify_webhook_signature(request.body, signature):
            logger.error("Invalid webhook signature")
            return Response({"error": "Invalid webhook signature"}, status=status.HTTP_401_UNAUTHORIZED)

        tx_ref = request.data.get('tx_ref')
        if not tx_ref:
            logger.error("Missing tx_ref in webhook payload")
            return Response({"error": "Missing tx_ref"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = Payment.objects.get(tx_ref=tx_ref)
        except Payment.DoesNotExist:
            logger.error(f"Payment with tx_ref {tx_ref} not found")
            return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

        verification = self.verify_chapa_payment(tx_ref)
        if verification['status']:
            payment.status = 'completed'
            payment.transaction_id = verification['data'].get('id')
            payment.job.status = 'paid'
        else:
            payment.status = 'failed'
            payment.job.status = 'pending_payment'
        payment.save()
        payment.job.save()
        self.send_notifications(payment.job, payment)
        return Response({"message": f"Payment {payment.status}"}, status=status.HTTP_200_OK)

    def verify_webhook_signature(self, payload, signature):
        if not signature or not settings.CHAPA_WEBHOOK_SECRET:
            return False
        expected_signature = hmac.new(
            settings.CHAPA_WEBHOOK_SECRET.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_signature, signature)

    def verify_chapa_payment(self, tx_ref):
        headers = {
            'Authorization': f'Bearer {settings.CHAPA_SECRET_KEY}',
            'Content-Type': 'application/json'
        }
        try:
            response = requests.get(f"{settings.CHAPA_VERIFY_ENDPOINT}/{tx_ref}", headers=headers)
            response.raise_for_status()
            data = response.json()
            if data.get('status') == 'success' and data['data']['status'] == 'success':
                return {'status': True, 'data': data['data']}
            return {'status': False, 'message': data.get('message', 'Verification failed')}
        except requests.RequestException as e:
            logger.error(f"Chapa verification failed for tx_ref {tx_ref}: {str(e)}")
            return {'status': False, 'message': str(e)}

    def send_notifications(self, job, payment):
        status_message = "confirmed" if payment.status == 'completed' else "failed"
        email_subject = f"Payment {status_message.capitalize()} for Job: {job.title}"
        email_message = (
            f"Dear {job.assigned_worker.user.first_name},\n\n"
            f"Client {job.client.first_name} has {status_message} payment for job: {job.title}.\n"
            f"Payment Method: {payment.payment_method}\n"
            f"Amount: {payment.amount or 'Not specified'}\n"
            f"Transaction ID: {payment.transaction_id or 'Not applicable'}\n"
            f"Status: {payment.status}\n\n"
            f"Best regards,\nSkillConnect Team"
        )
        sms_message = f"Payment {status_message} for job: {job.title}. Method: {payment.payment_method}. Status: {payment.status}."
        send_notification(job.assigned_worker.user, email_subject, email_message, sms_message)
        

class JobRequestView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Send a request to a worker for a job application.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['application_id'],
            properties={
                'application_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Application ID')
            },
        ),
        responses={
            201: JobRequestSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, id):
        try:
            job = Job.objects.get(pk=id, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data['application_id'] = data.get('application_id')
        serializer = JobRequestSerializer(data=data, context={'request': request, 'job_id': id})
        if serializer.is_valid():
            request_obj = serializer.save()
            worker = request_obj.application.worker.user
            client = request.user
            # Notify worker
            email_subject = f"New Job Request for {job.title}"
            email_message = (
                f"Dear {worker.first_name} {worker.last_name},\n\n"
                f"You have received a new job request from {client.first_name} {client.last_name} for the job '{job.title}'.\n"
                f"Job Details:\n"
                f"- Title: {job.title}\n"
                f"- Location: {job.location}\n"
                f"- Description: {job.description}\n\n"
                f"Client Contact Information:\n"
                f"- Email: {client.email}\n"
                f"- Phone: {client.phone_number or 'Not provided'}\n\n"
                f"Please log in to SkillConnect to review and respond to this request.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = (
                f"New job request for '{job.title}' from {client.first_name} {client.last_name}. "
                f"Contact: {client.email}, {client.phone_number or 'Not provided'}. Log in to respond."
            )
            send_notification(worker, email_subject, email_message, sms_message)
            # Notify client
            email_subject = f"Job Request Sent for {job.title}"
            email_message = (
                f"Dear {client.first_name} {client.last_name},\n\n"
                f"Your request for the job '{job.title}' has been successfully sent to {worker.first_name} {worker.last_name}.\n"
                f"Job Details:\n"
                f"- Title: {job.title}\n"
                f"- Location: {job.location}\n"
                f"- Description: {job.description}\n\n"
                f"Worker Contact Information:\n"
                f"- Email: {worker.email}\n"
                f"- Phone: {worker.phone_number or 'Not provided'}\n\n"
                f"You will be notified once the worker responds.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = (
                f"Your request for '{job.title}' has been sent to {worker.first_name} {worker.last_name}. "
                f"Contact: {worker.email}, {worker.phone_number or 'Not provided'}."
            )
            send_notification(client, email_subject, email_message, sms_message)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class JobRequestResponseView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="Accept or reject a job request.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['status'],
            properties={
                'status': openapi.Schema(type=openapi.TYPE_STRING, enum=['accepted', 'rejected'])
            },
        ),
        responses={
            200: JobRequestSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, pk, request_id):
        try:
            job = Job.objects.get(pk=pk)
            job_request = JobRequest.objects.get(id=request_id, application__job=job, application__worker=request.user.worker)
        except (Job.DoesNotExist, JobRequest.DoesNotExist):
            return Response({"error": "Job or request not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        serializer = JobRequestResponseSerializer(data=request.data, context={'job_request': job_request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        job_request.status = serializer.validated_data['status']
        job_request.save()
        if job_request.status == 'accepted':
            job_request.application.status = 'accepted'
            job_request.application.save()
            job.assigned_worker = request.user.worker
            job.status = 'in_progress'
            job.save()  # Ensure job is saved
            # Notify client
            email_subject = f"Worker Accepted Request for Job: {job.title}"
            email_message = (
                f"Dear {job.client.first_name},\n\n"
                f"Worker {request.user.first_name} {request.user.last_name} has accepted your request for job: {job.title}.\n"
                f"Contact them at:\nEmail: {request.user.email}\nPhone: {request.user.phone_number or 'Not provided'}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = (
                f"Worker {request.user.first_name} accepted job: {job.title}. "
                f"Contact: {request.user.email}, {request.user.phone_number or 'Not provided'}"
            )
            send_notification(job.client, email_subject, email_message, sms_message)
            # Notify worker
            email_subject = f"Assigned to Job: {job.title}"
            email_message = (
                f"Dear {request.user.first_name},\n\n"
                f"You have been assigned to job: {job.title}.\n"
                f"Contact the client at:\nEmail: {job.client.email}\nPhone: {job.client.phone_number or 'Not provided'}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = f"Assigned to job: {job.title}. Contact client: {job.client.email}"
            send_notification(request.user, email_subject, email_message, sms_message)
        else:
            job_request.application.status = 'rejected'
            job_request.application.save()
        serializer = JobRequestSerializer(job_request)
        return Response(serializer.data)
    

class JobStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Update job status to completed.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['status'],
            properties={
                'status': openapi.Schema(type=openapi.TYPE_STRING, enum=['completed'])
            },
        ),
        responses={
            200: JobSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def put(self, request, pk):
        try:
            job = Job.objects.get(pk=pk, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        serializer = JobStatusUpdateSerializer(data=request.data, context={'job': job})
        if serializer.is_valid():
            job.status = serializer.validated_data['status']
            job.save()
            # Notify worker
            email_subject = f"Job Completed: {job.title}"
            email_message = (
                f"Dear {job.assigned_worker.user.first_name},\n\n"
                f"The client has marked job '{job.title}' as completed.\n"
                f"You can now request payment via SkillConnect.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = f"Job {job.title} marked as completed. You can now request payment."
            send_notification(job.assigned_worker.user, email_subject, email_message, sms_message)
            serializer = JobSerializer(job)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class JobPaymentRequestView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="Worker requests payment for a completed job.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={},
            required=[],
        ),
        responses={
            201: PaymentRequestSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, pk):
        try:
            # Check if the job exists and has an accepted application for the worker
            job = Job.objects.get(pk=pk)
            if not JobApplication.objects.filter(job=job, worker=request.user.worker, status='accepted').exists():
                return Response({"error": "Job not assigned to you"}, status=status.HTTP_403_FORBIDDEN)
            if job.status != 'completed':
                return Response({"error": "Job is not completed"}, status=status.HTTP_400_BAD_REQUEST)
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = PaymentRequestSerializer(data={}, context={'request': request, 'worker': request.user.worker, 'job': job})
        if serializer.is_valid():
            payment_request = serializer.save()
            job.status = 'pending_payment'
            job.save()
            # Notify client
            email_subject = f"Payment Request for Job: {job.title}"
            email_message = (
                f"Dear {job.client.first_name},\n\n"
                f"Worker {request.user.first_name} {request.user.last_name} has requested payment for job: {job.title}.\n"
                f"Contact them at:\nEmail: {request.user.email}\nPhone: {request.user.phone_number or 'Not provided'}\n"
                f"Please process the payment via SkillConnect.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = (
                f"Payment request for job: {job.title} by {request.user.first_name}. "
                f"Contact: {request.user.email}, {request.user.phone_number or 'Not provided'}"
            )
            send_notification(job.client, email_subject, email_message, sms_message)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class JobFeedbackView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Submit feedback for a completed job.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['rating'],
            properties={
                'rating': openapi.Schema(type=openapi.TYPE_INTEGER, minimum=1, maximum=5, description='Rating from 1 to 5'),
                'review': openapi.Schema(type=openapi.TYPE_STRING, description='Optional review text', nullable=True),
            },
        ),
        responses={
            201: FeedbackSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, pk):
        try:
            job = Job.objects.get(pk=pk, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data['job'] = job.id
        serializer = FeedbackSerializer(data=data, context={'request': request, 'job': job})
        if serializer.is_valid():
            feedback = serializer.save()
            # Notify worker
            email_subject = f"New Feedback for Job: {job.title}"
            email_message = (
                f"Dear {job.assigned_worker.user.first_name},\n\n"
                f"Client {request.user.first_name} has submitted feedback for job: {job.title}.\n"
                f"Rating: {feedback.rating}/5\n"
                f"Review: {feedback.review or 'No review provided'}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = f"New feedback for job: {job.title}. Rating: {feedback.rating}/5."
            send_notification(job.assigned_worker.user, email_subject, email_message, sms_message)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class WorkerJobRequestsView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="List all job requests sent to the authenticated worker.",
        responses={
            200: JobRequestSerializer(many=True),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):
        requests = JobRequest.objects.filter(application__worker=request.user.worker)
        serializer = JobRequestSerializer(requests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ClientSentRequestsView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="List all job requests sent by the authenticated client.",
        responses={
            200: JobRequestSerializer(many=True),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):
        requests = JobRequest.objects.filter(application__job__client=request.user)
        serializer = JobRequestSerializer(requests, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class JobPaymentConfirmView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Confirm payment for a job in pending_payment status using Chapa (test mode) or cash.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['amount'],
            properties={
                'amount': openapi.Schema(type=openapi.TYPE_NUMBER, description='Payment amount')
            },
        ),
        responses={
            201: openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'payment': openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'job': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'client': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'worker': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'payment_method': openapi.Schema(type=openapi.TYPE_STRING),
                            'amount': openapi.Schema(type=openapi.TYPE_STRING),
                            'tx_ref': openapi.Schema(type=openapi.TYPE_STRING),
                            'transaction_id': openapi.Schema(type=openapi.TYPE_STRING),
                            'status': openapi.Schema(type=openapi.TYPE_STRING),
                            'created_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time')
                        }
                    ),
                    'checkout_url': openapi.Schema(type=openapi.TYPE_STRING)
                }
            ),
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, id):
        try:
            job = Job.objects.get(pk=id, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data['job'] = job.id  # Set job ID (integer) instead of Job object
        serializer = PaymentConfirmSerializer(data=data, context={'request': request, 'job': job})
        if serializer.is_valid():
            payment = serializer.save()
            if job.payment_method == 'chapa':
                try:
                    headers = {
                        'Authorization': f'Bearer {settings.CHAPA_SECRET_KEY}',
                        'Content-Type': 'application/json'
                    }
                    chapa_data = {
                        'amount': float(payment.amount),
                        'currency': 'ETB',
                        'email': request.user.email,
                        'tx_ref': payment.tx_ref,
                        'callback_url': settings.CHAPA_CALLBACK_URL,
                        'return_url': settings.CHAPA_RETURN_URL,
                        'first_name': request.user.first_name,
                        'last_name': request.user.last_name,
                        'title': f"Payment for job: {job.title}",
                        'description': f"Payment for job ID {job.id}"
                    }
                    response = requests.post(settings.CHAPA_PAYMENT_ENDPOINT, json=chapa_data, headers=headers)
                    response.raise_for_status()
                    chapa_response = response.json()
                    if chapa_response.get('status') == 'success':
                        payment.transaction_id = chapa_response['data']['id']
                        payment.save()
                        return Response({
                            'payment': PaymentConfirmSerializer(payment).data,
                            'checkout_url': chapa_response['data']['checkout_url']
                        }, status=status.HTTP_201_CREATED)
                    else:
                        logger.error(f"Chapa payment initiation failed: {chapa_response.get('message')}")
                        payment.delete()
                        return Response({"error": "Failed to initiate payment"}, status=status.HTTP_400_BAD_REQUEST)
                except requests.RequestException as e:
                    logger.error(f"Chapa payment request failed: {str(e)}")
                    payment.delete()
                    return Response({"error": "Payment service unavailable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            else:  # Cash payment
                payment.status = 'completed'
                payment.save()
                job.status = 'paid'
                job.save()
                # Notify worker
                email_subject = f"Payment Confirmed for Job: {job.title}"
                email_message = (
                    f"Dear {job.assigned_worker.user.first_name},\n\n"
                    f"Client {request.user.first_name} has confirmed payment for job: {job.title}.\n"
                    f"Payment Method: {payment.payment_method}\n"
                    f"Amount: {payment.amount or 'Not specified'}\n\n"
                    f"Best regards,\nSkillConnect Team"
                )
                sms_message = f"Payment confirmed for job: {job.title}. Method: {payment.payment_method}."
                send_notification(job.assigned_worker.user, email_subject, email_message, sms_message)
                return Response({'payment': PaymentConfirmSerializer(payment).data}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)