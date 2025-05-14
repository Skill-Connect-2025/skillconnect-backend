# apps/jobs/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from .models import Job
from .serializers import JobSerializer
from core.utils import IsClient

class JobCreateView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request):
        serializer = JobSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save(client=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class JobListView(generics.ListAPIView):
    queryset = Job.objects.filter(status='open')
    serializer_class = JobSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        skills = self.request.query_params.get('skills', None)
        location = self.request.query_params.get('location', None)
        if skills:
            queryset = queryset.filter(skills__icontains=skills)
        if location:
            queryset = queryset.filter(location__icontains=location)
        return queryset