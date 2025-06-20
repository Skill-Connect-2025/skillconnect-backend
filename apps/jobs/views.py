from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Job, JobApplication, JobRequest, Feedback, PaymentRequest, Transaction, JobImage, Category, JobCompletion, Dispute, Worker
from .serializers import (
    JobSerializer, JobApplicationSerializer, JobRequestSerializer,
    PaymentRequestSerializer, FeedbackSerializer, JobRequestResponseSerializer,
    JobStatusUpdateSerializer, ClientFeedbackSerializer, JobRequestResponseSerializer,
    DisputeSerializer, PublicWorkerProfileSerializer
)
from core.utils import IsClient, IsWorker
from apps.management.permissions import IsSuperuser
from .utils import initialize_payment, verify_payment, send_notification
from django.core.mail import send_mail
from django.conf import settings
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient
from django.contrib.auth import get_user_model
from django.views.decorators.csrf import csrf_exempt
from .serializers import TransactionSerializer
from django.core.exceptions import ObjectDoesNotExist
from rest_framework.serializers import ValidationError
import logging
import hmac
import hashlib
import requests
import re 
from django.db import models
from rest_framework import serializers

User = get_user_model()

logger = logging.getLogger(__name__)

def send_notification(user, subject, email_message, sms_message):
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

    if user.phone_number:
        if not re.match(r'^\+\d{9,15}$', user.phone_number):
            logger.warning(f"Invalid phone number format for user {user.id}: {user.phone_number}")
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
        operation_description="List all jobs",
        responses={
            200: openapi.Response(
                description='List of jobs',
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'title': openapi.Schema(type=openapi.TYPE_STRING),
                            'location': openapi.Schema(type=openapi.TYPE_STRING),
                            'skills': openapi.Schema(type=openapi.TYPE_STRING),
                            'description': openapi.Schema(type=openapi.TYPE_STRING),
                            'payment_method': openapi.Schema(type=openapi.TYPE_STRING),
                            'status': openapi.Schema(type=openapi.TYPE_STRING),
                            'created_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time')
                        }
                    )
                )
            ),
            401: 'Unauthorized'
        }
    )
    def get(self, request):  
        queryset = Job.objects.filter(client=self.request.user)
        serializer = JobSerializer(queryset, many=True)
        return Response(serializer.data)

class JobDetailView(generics.RetrieveAPIView):  
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsClient]

    def get_object(self):  
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
    def put(self, request, id):
        try:
            job = Job.objects.get(pk=id, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        
        # Store old data for comparison
        old_title = job.title
        old_location = job.location
        old_description = job.description
        
        serializer = JobSerializer(job, data=request.data, partial=True)
        if serializer.is_valid():
            updated_job = serializer.save()
            
            # Notify assigned worker if any and if significant changes were made
            if job.assigned_worker and (
                old_title != updated_job.title or
                old_location != updated_job.location or
                old_description != updated_job.description
            ):
                email_subject = f"Job Updated: {updated_job.title}"
                email_message = (
                    f"Dear {job.assigned_worker.user.first_name},\n\n"
                    f"The job '{updated_job.title}' has been updated by the client.\n"
                    f"Updated Details:\n"
                    f"- Title: {updated_job.title}\n"
                    f"- Location: {updated_job.location}\n"
                    f"- Description: {updated_job.description}\n\n"
                    f"Best regards,\nSkillConnect Team"
                )
                sms_message = f"Job '{updated_job.title}' has been updated. Please check the new details."
                send_notification(job.assigned_worker.user, email_subject, email_message, sms_message)
            
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
        
        # Store worker info before deletion for notification
        assigned_worker = job.assigned_worker
        
        # Notify assigned worker if any
        if assigned_worker:
            email_subject = f"Job Cancelled: {job.title}"
            email_message = (
                f"Dear {assigned_worker.user.first_name},\n\n"
                f"The job '{job.title}' has been cancelled by the client.\n"
                f"Job Details:\n"
                f"- Title: {job.title}\n"
                f"- Location: {job.location}\n"
                f"- Description: {job.description}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = f"Job '{job.title}' has been cancelled by the client."
            send_notification(assigned_worker.user, email_subject, email_message, sms_message)
        
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class OpenJobListView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="List all open jobs",
        responses={
            200: openapi.Response(
                description='List of open jobs',
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'title': openapi.Schema(type=openapi.TYPE_STRING),
                            'location': openapi.Schema(type=openapi.TYPE_STRING),
                            'skills': openapi.Schema(type=openapi.TYPE_STRING),
                            'description': openapi.Schema(type=openapi.TYPE_STRING),
                            'payment_method': openapi.Schema(type=openapi.TYPE_STRING),
                            'status': openapi.Schema(type=openapi.TYPE_STRING),
                            'created_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time')
                        }
                    )
                )
            ),
            401: 'Unauthorized'
        }
    )
    def get(self, request):
        jobs = Job.objects.filter(status='open')
        serializer = JobSerializer(jobs, many=True)
        return Response(serializer.data)

class JobApplicationView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="Apply to an open job or withdraw an existing application.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'worker_id': openapi.Schema(
                    type=openapi.TYPE_INTEGER,
                    description='Worker ID (ignored, auto-set to current user)'
                ),
                'action': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['apply', 'withdraw'],
                    description='Action to perform'
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
    def post(self, request, id):
        try:
            job = Job.objects.get(pk=id)
        except Job.DoesNotExist:
            logger.error(f"Job {id} not found for application")
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)
        
        action = request.data.get('action', 'apply')
        
        if action == 'withdraw':
            try:
                application = JobApplication.objects.get(
                    job=job,
                    worker=request.user.worker,
                    status='pending'
                )
                application.delete()
                
                # Notify client about withdrawal
                email_subject = f"Application Withdrawn: {job.title}"
                email_message = (
                    f"Dear {job.client.first_name},\n\n"
                    f"Worker {request.user.first_name} {request.user.last_name} has withdrawn their application for job: {job.title}.\n\n"
                    f"Best regards,\nSkillConnect Team"
                )
                sms_message = f"Worker {request.user.first_name} has withdrawn their application for job: {job.title}."
                send_notification(job.client, email_subject, email_message, sms_message)
                
                return Response(status=status.HTTP_204_NO_CONTENT)
            except JobApplication.DoesNotExist:
                return Response({"error": "No pending application found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Handle new application
        data = {
            'job': job.id,
            'worker_id': request.user.worker.id
        }
        
        serializer = JobApplicationSerializer(
            data=data,
            context={'request': request, 'job': job}
        )
        
        if serializer.is_valid():
            application = serializer.save()
            logger.info(f"Worker {request.user.worker.id} applied to job {id}")
            
            # Notify client about new application
            email_subject = f"New Application for Job: {job.title}"
            email_message = (
                f"Dear {job.client.first_name},\n\n"
                f"Worker {request.user.first_name} {request.user.last_name} has applied for your job '{job.title}'.\n"
                f"Please review the application in the SkillConnect platform.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = f"New application for job '{job.title}' from {request.user.first_name}. Review in SkillConnect."
            send_notification(job.client, email_subject, email_message, sms_message)
            
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
    permission_classes = [IsAuthenticated, IsWorker] 

    @swagger_auto_schema(
        operation_description="List all applications submitted by the authenticated worker.",
        responses={
            200: JobApplicationSerializer(many=True),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):  
        applications = JobApplication.objects.filter(worker=request.user.worker)
        serializer = JobApplicationSerializer(applications, many=True)
        return Response(serializer.data)
        
class JobRequestView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Send a request to a recommended worker for a job.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['worker_id'],
            properties={
                'worker_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Worker ID')
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
        data['job'] = job.id
        serializer = JobRequestSerializer(data=data, context={'request': request, 'job': job})
        
        if serializer.is_valid():
            request_obj = serializer.save()
            worker = request_obj.worker.user
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
                f"Please log in to SkillConnect to review and respond to this request.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = (
                f"New job request for '{job.title}' from {client.first_name} {client.last_name}. "
                f"Log in to SkillConnect to respond."
            )
            send_notification(worker, email_subject, email_message, sms_message)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ClientFeedbackView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="Submit feedback for a client after job completion.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['rating'],
            properties={
                'rating': openapi.Schema(type=openapi.TYPE_INTEGER, minimum=1, maximum=5),
                'review': openapi.Schema(type=openapi.TYPE_STRING, nullable=True),
            },
        ),
        responses={
            201: ClientFeedbackSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, pk):
        try:
            job = Job.objects.get(pk=pk)
            if job.assigned_worker != request.user.worker:
                return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = ClientFeedbackSerializer(
            data=request.data,
            context={'request': request, 'job': job, 'worker': request.user.worker}
        )
        
        if serializer.is_valid():
            feedback = serializer.save()
            
            # If both client and worker have submitted feedback, close the job
            if hasattr(job, 'feedback') and hasattr(job, 'client_feedback'):
                job.status = 'closed'
                job.save()

            # Notify client
            email_subject = f"New Feedback for Job: {job.title}"
            email_message = (
                f"Dear {job.client.first_name},\n\n"
                f"Worker {request.user.first_name} has submitted feedback for job: {job.title}.\n"
                f"Rating: {feedback.rating}/5\n"
                f"Review: {feedback.review or 'No review provided'}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = f"New feedback for job: {job.title}. Rating: {feedback.rating}/5."
            send_notification(job.client, email_subject, email_message, sms_message)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class JobApplicationResponseView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Accept or reject a worker's application.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['status'],
            properties={
                'status': openapi.Schema(type=openapi.TYPE_STRING, enum=['accepted', 'rejected'])
            },
        ),
        responses={
            200: JobApplicationSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, job_id, application_id):
        try:
            job = Job.objects.get(pk=job_id, client=request.user)
            application = JobApplication.objects.get(pk=application_id, job=job)
        except (Job.DoesNotExist, JobApplication.DoesNotExist):
            return Response({"error": "Job or application not found"}, status=status.HTTP_404_NOT_FOUND)

        if application.status != 'pending':
            return Response({"error": "Application has already been processed"}, status=status.HTTP_400_BAD_REQUEST)

        status_val = request.data.get('status')
        if status_val not in ['accepted', 'rejected']:
            return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)

        if status_val == 'accepted':
            if job.assigned_worker:
                return Response({"error": "Job already has an assigned worker"}, status=status.HTTP_400_BAD_REQUEST)
            job.assigned_worker = application.worker
            job.status = 'in_progress'
            job.save()

            # Notify worker (with client contact info)
            email_subject_worker = f"Application Accepted for {job.title}"
            email_message_worker = (
                f"Dear {application.worker.user.first_name},\n\n"
                f"Your application for job '{job.title}' has been accepted.\n"
                f"Contact the client at:\n"
                f"- Email: {job.client.email}\n"
                f"- Phone: {job.client.phone_number or 'Not provided'}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message_worker = f"Your application for '{job.title}' was accepted. Contact client for details."
            send_notification(application.worker.user, email_subject_worker, email_message_worker, sms_message_worker)

            # Notify client (with worker contact info)
            email_subject_client = f"You Accepted an Application for {job.title}"
            email_message_client = (
                f"Dear {job.client.first_name},\n\n"
                f"You have accepted {application.worker.user.first_name} {application.worker.user.last_name}'s application for job '{job.title}'.\n"
                f"Contact the worker at:\n"
                f"- Email: {application.worker.user.email}\n"
                f"- Phone: {application.worker.user.phone_number or 'Not provided'}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message_client = (
                f"You accepted {application.worker.user.first_name}'s application for '{job.title}'. "
                f"Contact: {application.worker.user.email}, {application.worker.user.phone_number or 'Not provided'}"
            )
            send_notification(job.client, email_subject_client, email_message_client, sms_message_client)

        else:  # Rejected
            # Notify worker (NO client contact info)
            email_subject_worker = f"Application Rejected for {job.title}"
            email_message_worker = (
                f"Dear {application.worker.user.first_name},\n\n"
                f"Your application for job '{job.title}' has been rejected by the client.\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message_worker = f"Your application for '{job.title}' was rejected."
            send_notification(application.worker.user, email_subject_worker, email_message_worker, sms_message_worker)

            # Notify client (confirmation, no contact info)
            email_subject_client = f"You Rejected an Application for {job.title}"
            email_message_client = (
                f"Dear {job.client.first_name},\n\n"
                f"You have rejected {application.worker.user.first_name} {application.worker.user.last_name}'s application for job '{job.title}'.\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message_client = f"You rejected {application.worker.user.first_name}'s application for '{job.title}'."
            send_notification(job.client, email_subject_client, email_message_client, sms_message_client)

        application.status = status_val
        application.save()

        serializer = JobApplicationSerializer(application)
        return Response(serializer.data)
    

class JobStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Mark job as completed (requires both client and worker to mark as completed)",
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
            job = Job.objects.get(pk=pk)
        except Job.DoesNotExist:
            return Response({"error": "Job not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if user is either client or worker
        if request.user != job.client and (not hasattr(request.user, 'worker') or request.user.worker != job.assigned_worker):
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        # Get or create completion status
        completion, created = JobCompletion.objects.get_or_create(job=job)

        # Update completion status based on user role
        if request.user == job.client:
            if completion.client_completed:
                return Response({"error": "You have already marked this job as completed"}, status=status.HTTP_400_BAD_REQUEST)
            completion.mark_client_completed()
            job.status = 'client_completed'
            job.save()
            
            # Notify worker
            email_subject = f"Job Marked as Completed by Client: {job.title}"
            email_message = (
                f"Dear {job.assigned_worker.user.first_name},\n\n"
                f"The client has marked job '{job.title}' as completed.\n"
                f"Please review and mark the job as completed if you agree.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = f"Client marked job {job.title} as completed. Please review and confirm."
            send_notification(job.assigned_worker.user, email_subject, email_message, sms_message)

        else:  # Worker
            if completion.worker_completed:
                return Response({"error": "You have already marked this job as completed"}, status=status.HTTP_400_BAD_REQUEST)
            completion.mark_worker_completed()
            job.status = 'worker_completed'
            job.save()
            
            # Notify client
            email_subject = f"Job Marked as Completed by Worker: {job.title}"
            email_message = (
                f"Dear {job.client.first_name},\n\n"
                f"The worker has marked job '{job.title}' as completed.\n"
                f"Please review and mark the job as completed if you agree.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = f"Worker marked job {job.title} as completed. Please review and confirm."
            send_notification(job.client, email_subject, email_message, sms_message)

        serializer = JobSerializer(job)
        return Response(serializer.data)

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

class PaymentConfirmView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Client confirms payment for a job.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['confirmation_code'],
            properties={
                'confirmation_code': openapi.Schema(type=openapi.TYPE_STRING)
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
    def post(self, request, id):
        try:
            job = Job.objects.get(pk=id, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)

        confirmation_code = request.data.get('confirmation_code')
        # ... your payment confirmation logic here ...
        # If payment is confirmed:
        job.status = 'completed'
        job.save()

        # Optionally, update transaction status if you have a Transaction model
        # transaction = Transaction.objects.filter(job=job).last()
        # if transaction:
        #     transaction.status = 'completed'
        #     transaction.save()

        # Notify worker
        email_subject = f"Payment Confirmed for Job: {job.title}"
        email_message = (
            f"Dear {job.assigned_worker.user.first_name},\n\n"
            f"The client has confirmed payment for job '{job.title}'.\n"
            f"Thank you for your work!\n\n"
            f"Best regards,\nSkillConnect Team"
        )
        sms_message = f"Payment for job {job.title} has been confirmed by the client."
        send_notification(job.assigned_worker.user, email_subject, email_message, sms_message)

        serializer = JobSerializer(job)
        return Response(serializer.data)

class PaymentCallbackView(APIView):
    @csrf_exempt
    def post(self, request):
        logger.debug(f"Received webhook: {request.data}")
        secret = settings.CHAPA_WEBHOOK_SECRET.encode('utf-8')
        signature = request.headers.get('Chapa-Signature')
        if signature:
            computed_signature = hmac.new(secret, request.body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(computed_signature, signature):
                logger.error('Invalid webhook signature')
                return Response({'error': 'Invalid webhook signature'}, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        tx_ref = data.get('tx_ref')
        payment_status = data.get('status')

        try:
            transaction = Transaction.objects.get(tx_ref=tx_ref)
            if payment_status.lower() == 'success':
                # Verify with Chapa
                verification = verify_payment(tx_ref)
                if verification.get('status') == 'success':
                    transaction.status = 'completed'
                    transaction.transaction_id = verification['data'].get('id')
                    transaction.save()

                    # Update job status to completed
                    job = transaction.job
                    job.status = 'completed'
                    job.save()

                    # Notify client
                    email_subject = f"Payment Confirmed for Job: {job.title}"
                    email_message = (
                        f"Dear {job.client.first_name},\n\n"
                        f"Your payment of {transaction.amount} ETB for job: {job.title} has been confirmed.\n"
                        f"Thank you for using SkillConnect.\n\n"
                        f"Best regards,\nSkillConnect Team"
                    )
                    sms_message = (
                        f"Payment of {transaction.amount} ETB for job: {job.title} confirmed."
                    )
                    send_notification(job.client, email_subject, email_message, sms_message)

                    # Notify worker
                    email_subject = f"Payment Received for Job: {job.title}"
                    email_message = (
                        f"Dear {job.assigned_worker.user.first_name},\n\n"
                        f"The payment of {transaction.amount} ETB for job: {job.title} has been confirmed.\n"
                        f"Thank you for your work.\n\n"
                        f"Best regards,\nSkillConnect Team"
                    )
                    sms_message = (
                        f"Payment of {transaction.amount} ETB for job: {job.title} received."
                    )
                    send_notification(job.assigned_worker.user, email_subject, email_message, sms_message)

                    logger.info(f'Payment verified for tx_ref: {tx_ref}')
                    return Response(
                        {'message': 'Payment verified'},
                        status=status.HTTP_200_OK
                    )
                else:
                    transaction.status = 'failed'
                    transaction.save()
                    logger.error(f'Payment verification failed for tx_ref: {tx_ref}')
                    return Response(
                        {'error': 'Verification failed'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            else:
                transaction.status = 'failed'
                transaction.save()
                logger.error(f'Payment failed for tx_ref: {tx_ref}')
                return Response(
                    {'error': 'Payment failed'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Transaction.DoesNotExist:
            logger.error(f'Transaction not found for tx_ref: {tx_ref}')
            return Response(
                {'error': 'Transaction not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class JobReviewsView(APIView):
    permission_classes = [IsAuthenticated]
    @swagger_auto_schema(
        operation_description="Get all reviews for a specific job.",
        responses={
            200: openapi.Response(
                description='List of reviews',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'worker_feedback': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'rating': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'review': openapi.Schema(type=openapi.TYPE_STRING),
                                'created_at': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        ),
                        'client_feedback': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'rating': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'review': openapi.Schema(type=openapi.TYPE_STRING),
                                'created_at': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    }
                )
            ),
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def get(self, request, job_id):
        try:
            job = Job.objects.get(id=job_id)
            
            # Check if user has permission to view reviews
            if not (request.user == job.client or 
                   (job.assigned_worker and request.user == job.assigned_worker.user)):
                return Response(
                    {"error": "Not authorized to view these reviews"},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            reviews = {
                'worker_feedback': None,
                'client_feedback': None
            }
            
            # Get worker feedback if exists
            if hasattr(job, 'feedback'):
                reviews['worker_feedback'] = {
                    'rating': job.feedback.rating,
                    'review': job.feedback.review,
                    'created_at': job.feedback.created_at
                }
            
            # Get client feedback if exists
            if hasattr(job, 'client_feedback'):
                reviews['client_feedback'] = {
                    'rating': job.client_feedback.rating,
                    'review': job.client_feedback.review,
                    'created_at': job.client_feedback.created_at
                }
            
            return Response(reviews, status=status.HTTP_200_OK)
        except Job.DoesNotExist:
            return Response(
                {"error": "Job not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class ClientJobCompletionView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Client marks a job as completed",
        responses={
            200: JobSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, job_id):
        try:
            job = Job.objects.get(pk=job_id, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)

        # Get or create completion status
        completion, created = JobCompletion.objects.get_or_create(job=job)

        if completion.client_completed:
            return Response({"error": "You have already marked this job as completed"}, status=status.HTTP_400_BAD_REQUEST)

        completion.mark_client_completed()
        # DO NOT set job.status = 'client_completed' here!
        # job.status is updated in mark_client_completed if both parties have completed

        # Notify worker
        email_subject = f"Job Marked as Completed by Client: {job.title}"
        email_message = (
            f"Dear {job.assigned_worker.user.first_name},\n\n"
            f"The client has marked job '{job.title}' as completed.\n"
            f"Please review and mark the job as completed if you agree.\n\n"
            f"Best regards,\nSkillConnect Team"
        )
        sms_message = f"Client marked job {job.title} as completed. Please review and confirm."
        send_notification(job.assigned_worker.user, email_subject, email_message, sms_message)

        # Reload job to get updated status
        job.refresh_from_db()
        serializer = JobSerializer(job)
        return Response(serializer.data)

class WorkerJobCompletionView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="Worker marks a job as completed",
        responses={
            200: JobSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, job_id):
        try:
            job = Job.objects.get(pk=job_id, assigned_worker=request.user.worker)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)

        # Get or create completion status
        completion, created = JobCompletion.objects.get_or_create(job=job)

        if completion.worker_completed:
            return Response({"error": "You have already marked this job as completed"}, status=status.HTTP_400_BAD_REQUEST)

        completion.mark_worker_completed()
        # DO NOT set job.status = 'worker_completed' here!
        # job.status is updated in mark_worker_completed if both parties have completed

        # Notify client
        email_subject = f"Job Marked as Completed by Worker: {job.title}"
        email_message = (
            f"Dear {job.client.first_name},\n\n"
            f"The worker has marked job '{job.title}' as completed.\n"
            f"Please review and mark the job as completed if you agree.\n\n"
            f"Best regards,\nSkillConnect Team"
        )
        sms_message = f"Worker marked job {job.title} as completed. Please review and confirm."
        send_notification(job.client, email_subject, email_message, sms_message)

        # Reload job to get updated status
        job.refresh_from_db()
        serializer = JobSerializer(job)
        return Response(serializer.data)

class DisputeCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Create a new dispute for a job",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['reported_user_id', 'dispute_type', 'description'],
            properties={
                'reported_user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                'dispute_type': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['payment', 'quality', 'behavior', 'other']
                ),
                'description': openapi.Schema(type=openapi.TYPE_STRING)
            }
        ),
        responses={
            201: DisputeSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, job_id):
        try:
            job = Job.objects.get(id=job_id)
            reported_user = User.objects.get(id=request.data.get('reported_user_id'))
        except (Job.DoesNotExist, User.DoesNotExist):
            return Response(
                {"error": "Job or user not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = DisputeSerializer(
            data=request.data,
            context={
                'request': request,
                'job': job,
                'reported_user': reported_user
            }
        )

        if serializer.is_valid():
            dispute = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DisputeListView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="List all disputes for the authenticated user",
        responses={
            200: DisputeSerializer(many=True),
            401: 'Unauthorized'
        }
    )
    def get(self, request):
        disputes = Dispute.objects.filter(
            models.Q(reported_by=request.user) | models.Q(reported_user=request.user)
        )
        serializer = DisputeSerializer(disputes, many=True)
        return Response(serializer.data)

class DisputeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get details of a specific dispute",
        responses={
            200: DisputeSerializer,
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def get(self, request, dispute_id):
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            if request.user != dispute.reported_by and request.user != dispute.reported_user:
                return Response(
                    {"error": "You don't have permission to view this dispute"},
                    status=status.HTTP_403_FORBIDDEN
                )
            serializer = DisputeSerializer(dispute)
            return Response(serializer.data)
        except Dispute.DoesNotExist:
            return Response(
                {"error": "Dispute not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class AdminDisputeListView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    @swagger_auto_schema(
        operation_description="List all disputes (admin only)",
        responses={
            200: DisputeSerializer(many=True),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):
        disputes = Dispute.objects.all()
        serializer = DisputeSerializer(disputes, many=True)
        return Response(serializer.data)

class AdminDisputeResolveView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    @swagger_auto_schema(
        operation_description="Resolve a dispute (admin only)",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['resolution'],
            properties={
                'resolution': openapi.Schema(type=openapi.TYPE_STRING)
            }
        ),
        responses={
            200: DisputeSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def post(self, request, dispute_id):
        try:
            dispute = Dispute.objects.get(id=dispute_id)
            if dispute.status in ['resolved', 'closed']:
                return Response(
                    {"error": "This dispute has already been resolved"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            resolution = request.data.get('resolution')
            if not resolution:
                return Response(
                    {"error": "Resolution text is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            dispute.mark_as_resolved(request.user, resolution)
            serializer = DisputeSerializer(dispute)
            return Response(serializer.data)
        except Dispute.DoesNotExist:
            return Response(
                {"error": "Dispute not found"},
                status=status.HTTP_404_NOT_FOUND
            )

class PublicWorkerProfileSerializer(serializers.ModelSerializer):
    rating_stats = serializers.SerializerMethodField()

    class Meta:
        model = Worker
        fields = [
            'id', 'user', 'skills', 'location', 'profile_pic', 'rating_stats'
        ]

    def get_rating_stats(self, obj):
        return obj.user.get_rating_stats()
    

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
            job_request = JobRequest.objects.get(id=request_id, worker=request.user.worker, job=job)
        except (Job.DoesNotExist, JobRequest.DoesNotExist):
            return Response({"error": "Job or request not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = JobRequestResponseSerializer(data=request.data, context={'job_request': job_request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        job_request.status = serializer.validated_data['status']
        job_request.save()
        
        if job_request.status == 'accepted':
            if job.status != 'open':
                return Response({"error": "Job is no longer available"}, status=status.HTTP_400_BAD_REQUEST)
            if job.assigned_worker:
                return Response({"error": "Job already has an assigned worker"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Create or update job application
            application, created = JobApplication.objects.get_or_create(
                job=job,
                worker=request.user.worker,
                defaults={'status': 'accepted'}
            )
            if not created:
                application.status = 'accepted'
                application.save()
            
            job.assigned_worker = request.user.worker
            job.status = 'in_progress'
            job.save()
            
            # Notify client with worker contact info
            email_subject_worker = f"Application Accepted for {job.title}"
            email_message_worker = (
                f"Dear {application.worker.user.first_name},\n\n"
                f"Your application for job '{job.title}' has been accepted.\n"
                f"Contact the client at:\n"
                f"- Email: {job.client.email}\n"
                f"- Phone: {job.client.phone_number or 'Not provided'}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message_worker = f"Your application for '{job.title}' was accepted. Contact client for details."
            send_notification(application.worker.user, email_subject_worker, email_message_worker, sms_message_worker)
            
            # Notify client (with worker contact info)
            email_subject_client = f"You Accepted an Application for {job.title}"
            email_message_client = (
                f"Dear {job.client.first_name},\n\n"
                f"You have accepted {application.worker.user.first_name} {application.worker.user.last_name}'s application for job '{job.title}'.\n"
                f"Contact the worker at:\n"
                f"- Email: {application.worker.user.email}\n"
                f"- Phone: {application.worker.user.phone_number or 'Not provided'}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message_client = (
                f"You accepted {application.worker.user.first_name}'s application for '{job.title}'. "
                f"Contact: {application.worker.user.email}, {application.worker.user.phone_number or 'Not provided'}"
            )
            send_notification(job.client, email_subject_client, email_message_client, sms_message_client)
        
        else:  # Rejected
            # Create or update job application
            application, created = JobApplication.objects.get_or_create(
                job=job,
                worker=request.user.worker,
                defaults={'status': 'rejected'}
            )
            if not created:
                application.status = 'rejected'
                application.save()
            
            # Notify client without contact info
            email_subject_worker = f"Application Rejected for {job.title}"
            email_message_worker = (
                f"Dear {job.client.first_name},\n\n"
                f"Worker {request.user.first_name} {request.user.last_name} has rejected your request for job: {job.title}.\n"
                f"Please consider sending requests to other workers.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message_worker = f"Worker {request.user.first_name} rejected job: {job.title}. Send requests to other workers."
            send_notification(job.client, email_subject_worker, email_message_worker, sms_message_worker)
            
            # Notify worker
            email_subject_client = f"Job Request Rejected: {job.title}"
            email_message_client = (
                f"Dear {request.user.first_name},\n\n"
                f"You have rejected the request for job: {job.title}.\n"
                f"Explore other job opportunities on SkillConnect.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message_client = f"You rejected the request for job: {job.title}. Explore other jobs on SkillConnect."
            send_notification(request.user, email_subject_client, email_message_client, sms_message_client)
        
        serializer = JobRequestSerializer(job_request)
        return Response(serializer.data)