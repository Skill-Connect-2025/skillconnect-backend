from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Job, JobApplication, JobRequest, Feedback, PaymentRequest
from .serializers import (
    JobSerializer, JobApplicationSerializer, JobRequestSerializer,
    PaymentRequestSerializer, FeedbackSerializer, JobRequestResponseSerializer,
    JobStatusUpdateSerializer
)
from core.utils import IsClient, IsWorker
from django.core.mail import send_mail
from django.conf import settings
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient
import logging

# Set up logging for notification failures
logger = logging.getLogger(__name__)

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
    def get_queryset(self):
        return Job.objects.filter(client=self.request.user)

class JobDetailView(APIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Retrieve details of a specific job (client must own the job).",
        responses={200: JobSerializer, 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found'}
    )
    def get(self, request, *args, **kwargs):
        job = self.get_object()
        if job.client != request.user:
            return Response({"error": "Not authorized to view this job"}, status=status.HTTP_403_FORBIDDEN)
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
    def put(self, request, pk):
        try:
            job = Job.objects.get(pk=pk, client=request.user)
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
                'worker_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Worker ID (auto-set to current user)')
            },
        ),
        responses={
            201: JobApplicationSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, pk):
        try:
            job = Job.objects.get(pk=pk)
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
        data = {'job': job.id, 'worker_id': request.user.worker.id}
        serializer = JobApplicationSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
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
    def get(self, request, pk):
        try:
            job = Job.objects.get(pk=pk, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        applications = job.applications.all()
        serializer = JobApplicationSerializer(applications, many=True)
        return Response(serializer.data)
    

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
    def post(self, request, pk):
        try:
            job = Job.objects.get(pk=pk, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data['application_id'] = data.get('application_id')
        serializer = JobRequestSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            request_obj = serializer.save()
            worker = request_obj.application.worker.user
            # Send email notification to worker
            email_subject = f"New Request for Job: {job.title}"
            email_message = (
                f"Dear {worker.first_name},\n\n"
                f"Client {request.user.username} has sent you a request for the job: {job.title}.\n"
                f"Please log in to SkillConnect to respond.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            try:
                send_mail(
                    subject=email_subject,
                    message=email_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[worker.email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Failed to send job request email to {worker.email}: {str(e)}")
            # Send SMS notification to worker (if phone number exists)
            if worker.phone_number:
                sms_message = f"New request for job: {job.title} from {request.user.username}. Log in to respond."
                try:
                    twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                    twilio_client.messages.create(
                        body=sms_message,
                        from_=settings.TWILIO_PHONE_NUMBER,
                        to=worker.phone_number
                    )
                except TwilioRestException as e:
                    logger.error(f"Failed to send job request SMS to {worker.phone_number}: {str(e)}")
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
        if serializer.is_valid():
            status = serializer.validated_data['status']
            job_request.status = status
            job_request.save()
            if status == 'accepted':
                job_request.application.status = 'accepted'
                job_request.application.save()
                job.assigned_worker = request.user.worker
                job.status = 'in_progress'
                job.save()
                # Notify client with worker contact details
                email_subject = f"Worker Accepted Request for Job: {job.title}"
                email_message = (
                    f"Dear {job.client.first_name},\n\n"
                    f"Worker {request.user.first_name} {request.user.last_name} has accepted your request for job: {job.title}.\n"
                    f"Contact them at:\nEmail: {request.user.email}\nPhone: {request.user.phone_number}\n\n"
                    f"Best regards,\nSkillConnect Team"
                )
                try:
                    send_mail(
                        subject=email_subject,
                        message=email_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[job.client.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    logger.error(f"Failed to send acceptance email to {job.client.email}: {str(e)}")
                # Send SMS to client (if phone number exists)
                if job.client.phone_number:
                    sms_message = (
                        f"Worker {request.user.first_name} accepted job: {job.title}. "
                        f"Contact: {request.user.email}, {request.user.phone_number}"
                    )
                    try:
                        twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                        twilio_client.messages.create(
                            body=sms_message,
                            from_=settings.TWILIO_PHONE_NUMBER,
                            to=job.client.phone_number
                        )
                    except TwilioRestException as e:
                        logger.error(f"Failed to send acceptance SMS to {job.client.phone_number}: {str(e)}")
                # Notify worker of assignment
                email_subject = f"Assigned to Job: {job.title}"
                email_message = (
                    f"Dear {request.user.first_name},\n\n"
                    f"You have been assigned to job: {job.title}.\n"
                    f"Contact the client at:\nEmail: {job.client.email}\nPhone: {job.client.phone_number or 'Not provided'}\n\n"
                    f"Best regards,\nSkillConnect Team"
                )
                try:
                    send_mail(
                        subject=email_subject,
                        message=email_message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[request.user.email],
                        fail_silently=False,
                    )
                except Exception as e:
                    logger.error(f"Failed to send assignment email to {request.user.email}: {str(e)}")
                # Send SMS to worker (if phone number exists)
                if request.user.phone_number:
                    sms_message = f"Assigned to job: {job.title}. Contact client: {job.client.email}"
                    try:
                        twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                        twilio_client.messages.create(
                            body=sms_message,
                            from_=settings.TWILIO_PHONE_NUMBER,
                            to=request.user.phone_number
                        )
                    except TwilioRestException as e:
                        logger.error(f"Failed to send assignment SMS to {request.user.phone_number}: {str(e)}")
            else:
                job_request.application.status = 'rejected'
                job_request.application.save()
            serializer = JobRequestSerializer(job_request)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

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
            try:
                send_mail(
                    subject=email_subject,
                    message=email_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[job.assigned_worker.user.email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Failed to send completion email to {job.assigned_worker.user.email}: {str(e)}")
            # Send SMS to worker (if phone number exists)
            if job.assigned_worker.user.phone_number:
                sms_message = f"Job {job.title} marked as completed. You can now request payment."
                try:
                    twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                    twilio_client.messages.create(
                        body=sms_message,
                        from_=settings.TWILIO_PHONE_NUMBER,
                        to=job.assigned_worker.user.phone_number
                    )
                except TwilioRestException as e:
                    logger.error(f"Failed to send completion SMS to {job.assigned_worker.user.phone_number}: {str(e)}")
            serializer = JobSerializer(job)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class JobPaymentRequestView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="Worker requests payment for a completed job.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'message': openapi.Schema(type=openapi.TYPE_STRING, description='Optional message')
            },
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
            job = Job.objects.get(pk=pk, assigned_worker=request.user.worker)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not assigned to you"}, status=status.HTTP_404_NOT_FOUND)
        data = request.data.copy()
        data['job'] = job.id
        data['worker'] = request.user.worker.id
        serializer = PaymentRequestSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            payment_request = serializer.save()
            job.status = 'pending_payment'
            job.save()
            # Notify client
            email_subject = f"Payment Request for Job: {job.title}"
            email_message = (
                f"Dear {job.client.first_name},\n\n"
                f"Worker {request.user.first_name} {request.user.last_name} has requested payment for job: {job.title}.\n"
                f"Contact them at:\nEmail: {request.user.email}\nPhone: {request.user.phone_number}\n"
                f"Please process the payment via SkillConnect.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            try:
                send_mail(
                    subject=email_subject,
                    message=email_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[job.client.email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Failed to send payment request email to {job.client.email}: {str(e)}")
            # Send SMS to client (if phone number exists)
            if job.client.phone_number:
                sms_message = (
                    f"Payment request for job: {job.title} by {request.user.first_name}. "
                    f"Contact: {request.user.email}, {request.user.phone_number}"
                )
                try:
                    twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                    twilio_client.messages.create(
                        body=sms_message,
                        from_=settings.TWILIO_PHONE_NUMBER,
                        to=job.client.phone_number
                    )
                except TwilioRestException as e:
                    logger.error(f"Failed to send payment request SMS to {job.client.phone_number}: {str(e)}")
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
        data['worker'] = job.assigned_worker.id
        data['client'] = request.user.id
        serializer = FeedbackSerializer(data=data, context={'request': request})
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
            try:
                send_mail(
                    subject=email_subject,
                    message=email_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[job.assigned_worker.user.email],
                    fail_silently=False,
                )
            except Exception as e:
                logger.error(f"Failed to send feedback email to {job.assigned_worker.user.email}: {str(e)}")
            if job.assigned_worker.user.phone_number:
                sms_message = f"New feedback for job: {job.title}. Rating: {feedback.rating}/5."
                try:
                    twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                    twilio_client.messages.create(
                        body=sms_message,
                        from_=settings.TWILIO_PHONE_NUMBER,
                        to=job.assigned_worker.user.phone_number
                    )
                except TwilioRestException as e:
                    logger.error(f"Failed to send feedback SMS to {job.assigned_worker.user.phone_number}: {str(e)}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserApplicationsView(APIView):
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
    def get(self, request, pk):
        try:
            job = Job.objects.get(pk=pk, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        applications = job.applications.all()
        serializer = JobApplicationSerializer(applications, many=True)
        return Response(serializer.data)