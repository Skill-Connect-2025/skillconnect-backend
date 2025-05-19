from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Job, JobApplication, JobRequest
from .serializers import JobSerializer, JobApplicationSerializer, JobRequestSerializer
from core.utils import IsClient, IsWorker
from django.core.mail import send_mail
from django.conf import settings

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

class JobListView(generics.ListAPIView):
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="List all jobs posted by the authenticated client.",
        responses={200: JobSerializer(many=True), 401: 'Unauthorized', 403: 'Forbidden'}
    )
    def get_queryset(self):
        return Job.objects.filter(client=self.request.user)

class JobDetailView(generics.RetrieveAPIView):
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
            # Send email notification to worker
            send_mail(
                subject=f"New Request for Job: {job.title}",
                message=f"Client {request.user.username} sent you a request for job: {job.title}. Log in to respond.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[request_obj.application.worker.user.email],
                fail_silently=True,
            )
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
        if job_request.status != 'pending':
            return Response({"error": "Request already processed"}, status=status.HTTP_400_BAD_REQUEST)
        status = request.data.get('status')
        if status not in ['accepted', 'rejected']:
            return Response({"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        job_request.status = status
        job_request.save()
        if status == 'accepted':
            job_request.application.status = 'accepted'
            job_request.application.save()
            # Notify client with worker contact details
            send_mail(
                subject=f"Worker Accepted Request for Job: {job.title}",
                message=f"Worker {request.user.username} accepted your request. Contact them at {request.user.email} or {request.user.phone_number}.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[job.client.email],
                fail_silently=True,
            )
        else:
            job_request.application.status = 'rejected'
            job_request.application.save()
        serializer = JobRequestSerializer(job_request)
        return Response(serializer.data)