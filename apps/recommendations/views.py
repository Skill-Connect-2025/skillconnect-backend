from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from apps.jobs.models import Job
from apps.users.models import Worker
from .models import MatchResult
from .serializers import MatchResultSerializer
from .utils import MatchEngine
from core.utils import IsClient, IsWorker
import logging

logger = logging.getLogger(__name__)

class JobWorkerRecommendationView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Get recommended workers for a specific job.",
        responses={
            200: MatchResultSerializer(many=True),
            401: 'Unauthorized',
            403: 'Forbidden',
            404: 'Not Found'
        }
    )
    def get(self, request, job_id):
        try:
            job = Job.objects.get(id=job_id, client=request.user)
        except Job.DoesNotExist:
            logger.error(f"Job {job_id} not found or not authorized for user {request.user.id}")
            return Response({"error": "Job not found or not authorized"}, status=status.HTTP_404_NOT_FOUND)

        # Check cached results
        existing_matches = MatchResult.objects.filter(job=job).order_by('-score')
        if existing_matches.exists():
            serializer = MatchResultSerializer(existing_matches, many=True)
            return Response(serializer.data)

        # Generate matches
        match_results = MatchEngine.match_job_to_workers(job)
        for result in match_results[:10]:  # Top 10
            MatchResult.objects.create(
                job=job,
                worker=result['worker'],
                score=result['score'],
                criteria=result['criteria']
            )

        matches = MatchResult.objects.filter(job=job).order_by('-score')
        serializer = MatchResultSerializer(matches, many=True)
        return Response(serializer.data)

class WorkerJobRecommendationView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="Get recommended jobs for the authenticated worker.",
        responses={
            200: MatchResultSerializer(many=True),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):
        worker = request.user.worker

        # Check cached results
        existing_matches = MatchResult.objects.filter(worker=worker, job__status='open').order_by('-score')
        if existing_matches.exists():
            serializer = MatchResultSerializer(existing_matches, many=True)
            return Response(serializer.data)

        # Generate matches
        match_results = MatchEngine.match_worker_to_jobs(worker)
        for result in match_results[:10]:  # Top 10
            MatchResult.objects.create(
                job=result['job'],
                worker=worker,
                score=result['score'],
                criteria=result['criteria']
            )

        matches = MatchResult.objects.filter(worker=worker, job__status='open').order_by('-score')
        serializer = MatchResultSerializer(matches, many=True)
        return Response(serializer.data)