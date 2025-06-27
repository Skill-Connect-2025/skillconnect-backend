import random
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .permissions import IsSuperuser, IsAdminUser
from django.contrib.auth import get_user_model
from .serializers import ManagementUserSerializer, ManagementUserUpdateSerializer
from .models import ManagementLog, NotificationLog, SystemAnalytics, NotificationTemplate
from apps.jobs.utils import send_notification
from django.db.models import Avg, Count, Sum
from django.utils import timezone
from datetime import timedelta
from apps.users.models import Worker, Client
from apps.jobs.models import Job, Transaction, Feedback, Dispute
from apps.jobs.serializers import DisputeSerializer
import logging
from rest_framework import viewsets
from rest_framework.decorators import action
from django.db.models import Q
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from .serializers import NotificationLogSerializer, SystemAnalyticsSerializer, BroadcastNotificationSerializer, ManagementLogSerializer, NotificationTemplateSerializer
from apps.recommendations.models import WeightConfig
from apps.jobs.models import Category
from apps.jobs.serializers import CategorySerializer
from apps.management.models import ManagementLog, PremiumPlan
from apps.recommendations.utils import MatchEngine
from apps.recommendations.models import MatchResult
from apps.recommendations.signals import invalidate_worker_matches, invalidate_job_matches
from apps.recommendations.serializers import MatchResultSerializer
from apps.jobs.models import Job
from apps.jobs.serializers import JobSerializer
from apps.users.serializers import UserSerializer, WorkerProfileSerializer
from apps.management.serializers import PremiumPlanSerializer

logger = logging.getLogger(__name__)
User = get_user_model()

class ManagementUserListView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    def get(self, request):
        """List all users with optional filtering by role."""
        role = request.query_params.get('role')
        users = User.objects.all()
        if role == 'client':
            users = users.filter(client__isnull=False)
        elif role == 'worker':
            users = users.filter(worker__isnull=False)
        serializer = ManagementUserSerializer(users, many=True)
        ManagementLog.objects.create(
            admin=request.user,
            action='list_users',
            details=f"Listed users with role filter: {role or 'all'}"
        )
        return Response(serializer.data)

class ManagementUserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    def get(self, request, user_id):
        """Retrieve detailed user profile."""
        try:
            user = User.objects.get(id=user_id)
            serializer = ManagementUserSerializer(user)
            ManagementLog.objects.create(
                admin=request.user,
                action='view_user',
                details=f"Viewed user {user.username} (ID: {user_id})"
            )
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    def put(self, request, user_id):
        """Update user profile."""
        try:
            user = User.objects.get(id=user_id)
            serializer = ManagementUserUpdateSerializer(
                user, data=request.data, partial=True, context={'request': request}
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

class ManagementUserViewSet(viewsets.ModelViewSet):
    """
    Admin API for managing users (CRUD, suspend, reset password).
    Only accessible to admin/superuser accounts.
    """
    queryset = User.objects.all()
    serializer_class = ManagementUserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return ManagementUserUpdateSerializer
        return self.serializer_class

    def perform_create(self, serializer):
        instance = serializer.save()
        ManagementLog.objects.create(
            admin=self.request.user,
            action='create_user',
            details=f"Created user {instance.username}"
        )

    def perform_destroy(self, instance):
        username = instance.username
        instance.delete()
        ManagementLog.objects.create(
            admin=self.request.user,
            action='delete_user',
            details=f"Deleted user {username}"
        )

    @action(detail=True, methods=['post'])
    def suspend(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save()
        ManagementLog.objects.create(
            admin=request.user,
            action='suspend_user',
            details=f'Suspended user {user.username}'
        )
        return Response({'status': 'user suspended'})

    @action(detail=True, methods=['post'])
    def reset_password(self, request, pk=None):
        user = self.get_object()
        new_password = request.data.get('new_password')
        if not new_password:
            return Response({'error': 'new_password required'}, status=400)
        user.set_password(new_password)
        user.save()
        ManagementLog.objects.create(
            admin=request.user,
            action='reset_password',
            details=f'Reset password for user {user.username}'
        )
        return Response({'status': 'password reset'})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsAdminUser])
    def grant_premium(self, request, pk=None):
        """
        Admin can grant premium to a user for a given plan.
        """
        user = self.get_object()
        plan_id = request.data.get('plan_id')
        try:
            plan = PremiumPlan.objects.get(id=plan_id)
        except PremiumPlan.DoesNotExist:
            return Response({'detail': 'Plan not found.'}, status=404)
        user.is_premium = True
        user.premium_until = timezone.now() + timezone.timedelta(days=plan.duration_days)
        user.save()
        return Response({'detail': f'Granted {plan.name} premium to user.'})

class SystemAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Admin API for viewing daily platform analytics (auto-generates today's analytics if missing).
    Only accessible to admin/superuser accounts.
    """
    queryset = SystemAnalytics.objects.all()
    serializer_class = SystemAnalyticsSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def list(self, request, *args, **kwargs):
        from django.utils import timezone
        today = timezone.now().date()
        if not SystemAnalytics.objects.filter(date=today).exists():
            # Generate today's analytics
            SystemAnalytics.objects.create(
                date=today,
                total_users=User.objects.count(),
                total_clients=Client.objects.count(),
                total_workers=Worker.objects.count(),
                total_jobs=Job.objects.count(),
                completed_jobs=Job.objects.filter(status='completed').count(),
                total_transactions=Transaction.objects.count(),
                total_transaction_amount=Transaction.objects.aggregate(total=Sum('amount'))['total'] or 0,
                average_rating=Feedback.objects.aggregate(avg=Avg('rating'))['avg'] or 0
            )
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary of key metrics."""
        try:
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            
            today_analytics = SystemAnalytics.objects.filter(date=today).first()
            yesterday_analytics = SystemAnalytics.objects.filter(date=yesterday).first()

            if not today_analytics:
                self.generate_daily(request)

            return Response({
                'today': SystemAnalyticsSerializer(today_analytics).data if today_analytics else None,
                'yesterday': SystemAnalyticsSerializer(yesterday_analytics).data if yesterday_analytics else None,
                'trends': {
                    'new_users': User.objects.filter(
                        date_joined__date=today
                    ).count(),
                    'new_jobs': Job.objects.filter(
                        created_at__date=today
                    ).count(),
                    'completed_jobs': Job.objects.filter(
                        status='completed',
                        updated_at__date=today
                    ).count(),
                    'total_revenue': Transaction.objects.filter(
                        created_at__date=today
                    ).aggregate(total=Sum('amount'))['total'] or 0
                }
            })
        except Exception as e:
            logger.error(f"Error getting analytics summary: {str(e)}")
            return Response(
                {'error': 'Failed to get analytics summary'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DisputeManagementViewSet(viewsets.ModelViewSet):
    """
    Admin API for managing disputes (CRUD, resolve, statistics).
    Only accessible to admin/superuser accounts.
    """
    queryset = Dispute.objects.all()
    serializer_class = DisputeSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        queryset = super().get_queryset()
        status = self.request.query_params.get('status', None)
        dispute_type = self.request.query_params.get('type', None)
        
        if status:
            queryset = queryset.filter(status=status)
        if dispute_type:
            queryset = queryset.filter(dispute_type=dispute_type)
            
        return queryset

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        dispute = self.get_object()
        resolution = request.data.get('resolution')
        suspend_user = request.data.get('suspend_user', False)
        suspend_days = request.data.get('suspend_days', 0)
        flag_user = request.data.get('flag_user', False)
        flag_reason = request.data.get('flag_reason', '')
        user_to_act = dispute.reported_user
        if not resolution:
            return Response({'error': 'Resolution message is required'}, status=status.HTTP_400_BAD_REQUEST)
        if dispute.status in ['resolved', 'closed']:
            return Response({'error': 'Dispute is already resolved or closed'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            dispute.mark_as_resolved(request.user, resolution)
            # Suspend user if requested
            if suspend_user and suspend_days > 0:
                user_to_act.is_active = False
                user_to_act.suspended_until = timezone.now() + timedelta(days=int(suspend_days))
                user_to_act.save()
                ManagementLog.objects.create(
                    admin=request.user,
                    action='suspend_user_dispute',
                    details=f'Suspended user {user_to_act.username} for {suspend_days} days due to dispute {dispute.id}'
                )
            # Flag user if requested
            if flag_user:
                user_to_act.flagged = True
                user_to_act.flag_reason = flag_reason or f'Flagged by admin during dispute {dispute.id}'
                user_to_act.save()
                ManagementLog.objects.create(
                    admin=request.user,
                    action='flag_user_dispute',
                    details=f'Flagged user {user_to_act.username} for dispute {dispute.id}: {user_to_act.flag_reason}'
                )
            # Notify both parties about the resolution
            email_subject = "Dispute Resolution Update"
            email_message = (
                f"Dear {dispute.reported_by.first_name},\n\n"
                f"Your dispute regarding job '{dispute.job.title}' has been resolved.\n"
                f"Resolution: {resolution}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            send_notification(
                dispute.reported_by,
                email_subject,
                email_message,
                f"Your dispute has been resolved. Resolution: {resolution}"
            )
            email_message = (
                f"Dear {dispute.reported_user.first_name},\n\n"
                f"The dispute regarding job '{dispute.job.title}' has been resolved.\n"
                f"Resolution: {resolution}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            send_notification(
                dispute.reported_user,
                email_subject,
                email_message,
                f"The dispute has been resolved. Resolution: {resolution}"
            )
            # Log the action
            ManagementLog.objects.create(
                admin=request.user,
                action='resolve_dispute',
                details=f'Resolved dispute {dispute.id} for job {dispute.job.id}'
            )
            return Response(self.get_serializer(dispute).data)
        except Exception as e:
            logger.error(f"Error resolving dispute: {str(e)}")
            return Response({'error': 'Failed to resolve dispute'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        """Close a resolved dispute."""
        dispute = self.get_object()
        
        if dispute.status != 'resolved':
            return Response(
                {'error': 'Only resolved disputes can be closed'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            dispute.status = 'closed'
            dispute.save()
            
            # Log the action
            ManagementLog.objects.create(
                admin=request.user,
                action='close_dispute',
                details=f'Closed dispute {dispute.id} for job {dispute.job.id}'
            )
            
            return Response(self.get_serializer(dispute).data)
            
        except Exception as e:
            logger.error(f"Error closing dispute: {str(e)}")
            return Response(
                {'error': 'Failed to close dispute'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get dispute statistics."""
        try:
            total_disputes = Dispute.objects.count()
            disputes_by_status = dict(Dispute.objects.values_list('status').annotate(count=Count('id')))
            disputes_by_type = dict(Dispute.objects.values_list('dispute_type').annotate(count=Count('id')))
            
            # Calculate average resolution time
            resolved_disputes = Dispute.objects.filter(status='resolved')
            avg_resolution_time = None
            if resolved_disputes.exists():
                resolution_times = [
                    (d.resolved_at - d.created_at).total_seconds() / 3600  # Convert to hours
                    for d in resolved_disputes
                    if d.resolved_at
                ]
                if resolution_times:
                    avg_resolution_time = sum(resolution_times) / len(resolution_times)
            
            return Response({
                'total_disputes': total_disputes,
                'disputes_by_status': disputes_by_status,
                'disputes_by_type': disputes_by_type,
                'average_resolution_time_hours': avg_resolution_time
            })
            
        except Exception as e:
            logger.error(f"Error getting dispute statistics: {str(e)}")
            return Response(
                {'error': 'Failed to get dispute statistics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CategoryViewSet(viewsets.ModelViewSet):
    """
    Admin API for managing job/service categories (CRUD).
    Only accessible to admin/superuser accounts.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

class RecommendationManagementView(APIView):
    """
    Admin API to get recommendation system metrics and statistics.
    Only accessible to admin/superuser accounts.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    def get(self, request):
        # Get match quality metrics
        match_quality = {
            'average_score': 0,
            'score_distribution': {},
            'acceptance_rate': 0
        }

        # Get algorithm metrics
        algorithm_metrics = {
            'skill_match_weight': MatchEngine.DEFAULT_SKILL_WEIGHT,
            'experience_weight': MatchEngine.DEFAULT_EXPERIENCE_WEIGHT,
            'rating_weight': MatchEngine.DEFAULT_RATING_WEIGHT,
            'location_weight': MatchEngine.DEFAULT_LOCATION_WEIGHT
        }

        # Get performance metrics
        performance_metrics = {
            'average_response_time': 0,
            'cache_hit_rate': 0,
            'embedding_quality': 0
        }

        return Response({
            'match_quality': match_quality,
            'algorithm_metrics': algorithm_metrics,
            'performance_metrics': performance_metrics,
        })

    @swagger_auto_schema(
        operation_description="Update recommendation algorithm weights",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'skill_match_weight': openapi.Schema(type=openapi.TYPE_NUMBER),
                'experience_weight': openapi.Schema(type=openapi.TYPE_NUMBER),
                'rating_weight': openapi.Schema(type=openapi.TYPE_NUMBER),
                'location_weight': openapi.Schema(type=openapi.TYPE_NUMBER),
            }
        ),
        responses={
            200: openapi.Response(description="Weights updated successfully"),
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def put(self, request):
        weights = request.data
        total_weight = sum(weights.values())

        if not 0.99 <= total_weight <= 1.01:  # Allow for small floating-point errors
            return Response(
                {"error": "Weights must sum to 1.0"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update weights in the MatchEngine class
        MatchEngine.DEFAULT_SKILL_WEIGHT = weights.get('skill_match_weight', MatchEngine.DEFAULT_SKILL_WEIGHT)
        MatchEngine.DEFAULT_EXPERIENCE_WEIGHT = weights.get('experience_weight', MatchEngine.DEFAULT_EXPERIENCE_WEIGHT)
        MatchEngine.DEFAULT_RATING_WEIGHT = weights.get('rating_weight', MatchEngine.DEFAULT_RATING_WEIGHT)
        MatchEngine.DEFAULT_LOCATION_WEIGHT = weights.get('location_weight', MatchEngine.DEFAULT_LOCATION_WEIGHT)

        # Log the weight update
        ManagementLog.objects.create(
            admin=request.user,
            action='update_recommendation_weights',
            details=f"Updated recommendation weights: {weights}"
        )

        return Response({"message": "Recommendation weights updated successfully"})

class JobViewSet(viewsets.ModelViewSet):
    """
    Admin API for managing jobs (CRUD).
    Only accessible to admin/superuser accounts.
    """
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

class RecommendedWorkersForJobView(APIView):
    """
    Admin API to get recommended workers for a specific job (for a client).
    Only accessible to admin/superuser accounts.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    def get(self, request, job_id):
        from apps.jobs.models import Job
        try:
            job = Job.objects.get(id=job_id)
        except Job.DoesNotExist:
            return Response({"detail": "Job not found."}, status=404)
        results = MatchEngine.match_job_to_workers(job)
        # Serialize workers and include score/criteria
        data = [
            {
                "worker": WorkerProfileSerializer(r["worker"]).data,
                "score": r["score"],
                "criteria": r["criteria"]
            }
            for r in results
        ]
        return Response(data)

class RecommendedJobsForWorkerView(APIView):
    """
    Admin API to get recommended jobs for a specific worker.
    Only accessible to admin/superuser accounts.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    def get(self, request, worker_id):
        from apps.users.models import Worker
        from apps.jobs.serializers import JobSerializer
        try:
            worker = Worker.objects.get(id=worker_id)
        except Worker.DoesNotExist:
            return Response({"detail": "Worker not found."}, status=404)
        results = MatchEngine.match_worker_to_jobs(worker)
        # Serialize jobs and include score/criteria
        data = [
            {
                "job": JobSerializer(r["job"]).data,
                "score": r["score"],
                "criteria": r["criteria"]
            }
            for r in results
        ]
        return Response(data)

class PremiumPlanViewSet(viewsets.ModelViewSet):
    """
    Admin API for managing premium subscription plans.
    """
    queryset = PremiumPlan.objects.all()
    serializer_class = PremiumPlanSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]