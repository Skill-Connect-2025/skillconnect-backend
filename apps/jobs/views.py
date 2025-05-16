from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import Job
from .serializers import JobSerializer
from core.utils import IsClient

class JobCreateView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Create a new job. Photos are optional.",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['title', 'location', 'skills', 'description', 'category_id', 'payment_method'],
            properties={
                'title': openapi.Schema(type=openapi.TYPE_STRING, description='Job title (e.g., Fix my sink)'),
                'location': openapi.Schema(type=openapi.TYPE_STRING, description='Job location (e.g., Addis Ababa)'),
                'skills': openapi.Schema(type=openapi.TYPE_STRING, description='Comma-separated skills (e.g., Plumbing)'),
                'description': openapi.Schema(type=openapi.TYPE_STRING, description='Job description'),
                'category_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Category ID (e.g., 1 for Plumbing)'),
                'payment_method': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['telebirr', 'chapa', 'e_birr', 'cash'],
                    description='Payment method'
                ),
                'uploaded_images': openapi.Schema(
                    type=openapi.TYPE_FILE,
                    description='Optional image files',
                    nullable=True
                ),
            },
        ),
        consumes=['multipart/form-data'],
        produces=['application/json'],
        responses={
            201: JobSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden'
        },
        security=[{'Token': []}]
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
        responses={200: JobSerializer(many=True), 401: 'Unauthorized', 403: 'Forbidden'},
        security=[{'Token': []}]
    )
    def get_queryset(self):
        return Job.objects.filter(client=self.request.user)

class JobDetailView(generics.RetrieveAPIView):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Retrieve details of a specific job (client must own the job).",
        responses={200: JobSerializer, 401: 'Unauthorized', 403: 'Forbidden', 404: 'Not Found'},
        security=[{'Token': []}]
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
                'title': openapi.Schema(type=openapi.TYPE_STRING, description='Job title (e.g., Fix my sink)'),
                'location': openapi.Schema(type=openapi.TYPE_STRING, description='Job location (e.g., Addis Ababa)'),
                'skills': openapi.Schema(type=openapi.TYPE_STRING, description='Comma-separated skills (e.g., Plumbing)'),
                'description': openapi.Schema(type=openapi.TYPE_STRING, description='Job description'),
                'category_id': openapi.Schema(type=openapi.TYPE_INTEGER, description='Category ID (e.g., 1 for Plumbing)'),
                'payment_method': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['telebirr', 'chapa', 'e_birr', 'cash'],
                    description='Payment method'
                ),
                'uploaded_images': openapi.Schema(
                    type=openapi.TYPE_FILE,
                    description='Optional image files',
                    nullable=True
                ),
            },
        ),
        consumes=['multipart/form-data'],
        produces=['application/json'],
        responses={
            200: JobSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        },
        security=[{'Token': []}]
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
        },
        security=[{'Token': []}]
    )
    def delete(self, request, pk):
        try:
            job = Job.objects.get(pk=pk, client=request.user)
        except Job.DoesNotExist:
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)