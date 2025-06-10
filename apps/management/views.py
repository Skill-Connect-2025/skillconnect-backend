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

class ManagementUserSuspendView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    def post(self, request, user_id):
        """Suspend or reactivate a user."""
        try:
            user = User.objects.get(id=user_id)
            is_active = request.data.get('is_active', False)
            reason = request.data.get('reason', '')
            if user.is_active == is_active:
                return Response({"error": f"User is already {'active' if is_active else 'suspended'}"}, status=status.HTTP_400_BAD_REQUEST)
            user.is_active = is_active
            user.save()
            action = 'suspended' if not is_active else 'reactivated'
            email_subject = f"Account {action.capitalize()}"
            email_message = (
                f"Dear {user.first_name},\n\n"
                f"Your account has been {action}.\n"
                f"Reason: {reason or 'No reason provided'}\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = f"Your account has been {action}. Reason: {reason or 'None'}"
            send_notification(user, email_subject, email_message, sms_message)
            ManagementLog.objects.create(
                admin=request.user,
                action=f'{action}_user',
                details=f"{action.capitalize()} user {user.username} (ID: {user_id}). Reason: {reason}"
            )
            return Response({"message": f"User {action}"})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

class ManagementUserResetPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    def post(self, request, user_id):
        """Generate and send a password reset code."""
        try:
            user = User.objects.get(id=user_id)
            reset_code = str(random.randint(100000, 999999))
            user.reset_code = reset_code
            user.save()
            email_subject = "Password Reset Request"
            email_message = (
                f"Dear {user.first_name},\n\n"
                f"Your password reset code is: {reset_code}\n"
                f"Please use this code to reset your password.\n\n"
                f"Best regards,\nSkillConnect Team"
            )
            sms_message = f"Your password reset code is: {reset_code}"
            send_notification(user, email_subject, email_message, sms_message)
            ManagementLog.objects.create(
                admin=request.user,
                action='reset_password',
                details=f'Reset password for user {user.username} (ID: {user_id})'
            )
            return Response({"message": "Password reset code sent"})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

class ManagementUserViewSet(viewsets.ModelViewSet):
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

class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NotificationLog.objects.all()
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get_queryset(self):
        queryset = super().get_queryset()
        if not self.request.user.is_superuser:
            return queryset.filter(recipient=self.request.user)
        return queryset

class SystemAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SystemAnalytics.objects.all()
    serializer_class = SystemAnalyticsSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    @action(detail=False, methods=['post'])
    def generate_daily(self, request):
        """Generate daily analytics."""
        try:
            today = timezone.now().date()
            analytics = SystemAnalytics.objects.create(
                date=today,
                total_users=User.objects.count(),
                total_clients=Client.objects.count(),
                total_workers=Worker.objects.count(),
                total_jobs=Job.objects.count(),
                completed_jobs=Job.objects.filter(status='completed').count(),
                total_transactions=Transaction.objects.count(),
                total_transaction_amount=Transaction.objects.aggregate(
                    total=Sum('amount')
                )['total'] or 0,
                average_rating=Feedback.objects.aggregate(
                    avg=Avg('rating')
                )['avg'] or 0
            )
            return Response(
                SystemAnalyticsSerializer(analytics).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            logger.error(f"Error generating daily analytics: {str(e)}")
            return Response(
                {'error': 'Failed to generate analytics'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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

class BroadcastNotificationViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, IsSuperuser]

    def create(self, request):
        serializer = BroadcastNotificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        recipients = self._get_recipients(data['recipients'])
        
        success_count = 0
        error_count = 0
        
        for user in recipients:
            try:
                notification = NotificationLog.objects.create(
                    recipient=user,
                    subject=data.get('subject', ''),
                    message=data['message'],
                    channel=data['channel']
                )
                
                send_notification(
                    user=user,
                    subject=data.get('subject', ''),
                    message=data['message'],
                    channel=data['channel']
                )
                
                notification.status = 'sent'
                notification.sent_at = timezone.now()
                notification.save()
                success_count += 1
                
            except Exception as e:
                logger.error(f"Error sending notification to {user.username}: {str(e)}")
                if notification:
                    notification.status = 'failed'
                    notification.error_message = str(e)
                    notification.save()
                error_count += 1

        ManagementLog.objects.create(
            admin=request.user,
            action='broadcast_notification',
            details=f"Sent broadcast to {success_count} users ({error_count} failed)"
        )

        return Response({
            'success_count': success_count,
            'error_count': error_count
        })

    def _get_recipients(self, recipient_type):
        if recipient_type == 'all':
            return User.objects.filter(is_active=True)
        elif recipient_type == 'clients':
            return User.objects.filter(client__isnull=False, is_active=True)
        elif recipient_type == 'workers':
            return User.objects.filter(worker__isnull=False, is_active=True)
        return User.objects.none()

class ManagementLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ManagementLog.objects.all()
    serializer_class = ManagementLogSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

class DisputeManagementViewSet(viewsets.ModelViewSet):
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
        """Resolve a dispute with a resolution message."""
        dispute = self.get_object()
        resolution = request.data.get('resolution')
        
        if not resolution:
            return Response(
                {'error': 'Resolution message is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if dispute.status in ['resolved', 'closed']:
            return Response(
                {'error': 'Dispute is already resolved or closed'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            dispute.mark_as_resolved(request.user, resolution)
            
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
            return Response(
                {'error': 'Failed to resolve dispute'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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

class ManagementUserSearchView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    @swagger_auto_schema(
        operation_description="Search users with filters",
        manual_parameters=[
            openapi.Parameter('query', openapi.IN_QUERY, description="Search query", type=openapi.TYPE_STRING),
            openapi.Parameter('role', openapi.IN_QUERY, description="User role (client/worker)", type=openapi.TYPE_STRING),
            openapi.Parameter('status', openapi.IN_QUERY, description="User status (active/suspended)", type=openapi.TYPE_STRING),
            openapi.Parameter('date_from', openapi.IN_QUERY, description="Start date", type=openapi.TYPE_STRING),
            openapi.Parameter('date_to', openapi.IN_QUERY, description="End date", type=openapi.TYPE_STRING),
        ],
        responses={
            200: ManagementUserSerializer(many=True),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):
        query = request.query_params.get('query', '')
        role = request.query_params.get('role')
        status = request.query_params.get('status')
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')

        users = User.objects.all()

        if query:
            users = users.filter(
                Q(username__icontains=query) |
                Q(email__icontains=query) |
                Q(phone_number__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            )

        if role:
            if role == 'client':
                users = users.filter(client__isnull=False)
            elif role == 'worker':
                users = users.filter(worker__isnull=False)

        if status:
            users = users.filter(is_active=(status == 'active'))

        if date_from:
            users = users.filter(date_joined__gte=date_from)
        if date_to:
            users = users.filter(date_joined__lte=date_to)

        serializer = ManagementUserSerializer(users, many=True)
        return Response(serializer.data)

class ManagementUserBulkActionView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    @swagger_auto_schema(
        operation_description="Perform bulk actions on users",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['user_ids', 'action'],
            properties={
                'user_ids': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_INTEGER)),
                'action': openapi.Schema(type=openapi.TYPE_STRING, enum=['suspend', 'activate', 'delete'])
            }
        ),
        responses={
            200: openapi.Response(description="Action completed successfully"),
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def post(self, request):
        user_ids = request.data.get('user_ids', [])
        action = request.data.get('action')

        if not user_ids or not action:
            return Response(
                {"error": "user_ids and action are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        users = User.objects.filter(id__in=user_ids)
        
        if action == 'suspend':
            users.update(is_active=False)
            action_type = 'bulk_suspend'
        elif action == 'activate':
            users.update(is_active=True)
            action_type = 'bulk_activate'
        elif action == 'delete':
            users.delete()
            action_type = 'bulk_delete'
        else:
            return Response(
                {"error": "Invalid action"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Log the bulk action
        ManagementLog.objects.create(
            admin=request.user,
            action=action_type,
            details=f"Performed {action} on {len(user_ids)} users"
        )

        return Response({"message": f"Successfully performed {action} on {len(user_ids)} users"})

class AnalyticsDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    @swagger_auto_schema(
        operation_description="Get detailed analytics dashboard with trend analysis",
        manual_parameters=[
            openapi.Parameter('period', openapi.IN_QUERY, description="Time period (daily/weekly/monthly)", type=openapi.TYPE_STRING),
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Start date", type=openapi.TYPE_STRING),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="End date", type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response(
                description="Analytics dashboard data",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'user_metrics': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'total_users': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'active_users': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'new_users': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'user_growth_rate': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'user_retention_rate': openapi.Schema(type=openapi.TYPE_NUMBER),
                            }
                        ),
                        'job_metrics': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'total_jobs': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'completed_jobs': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'active_jobs': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'completion_rate': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'average_job_duration': openapi.Schema(type=openapi.TYPE_NUMBER),
                            }
                        ),
                        'financial_metrics': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'total_transactions': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'total_volume': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'average_transaction': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'payment_method_distribution': openapi.Schema(type=openapi.TYPE_OBJECT),
                            }
                        ),
                        'quality_metrics': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'average_rating': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'rating_distribution': openapi.Schema(type=openapi.TYPE_OBJECT),
                                'dispute_rate': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'resolution_rate': openapi.Schema(type=openapi.TYPE_NUMBER),
                            }
                        ),
                        'trends': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'user_growth': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                                'job_activity': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                                'revenue': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_OBJECT)),
                            }
                        ),
                    }
                )
            ),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):
        period = request.query_params.get('period', 'daily')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        # Calculate user metrics
        user_metrics = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'new_users': User.objects.filter(date_joined__gte=start_date).count() if start_date else 0,
            'user_growth_rate': self._calculate_growth_rate(User, 'date_joined', period),
            'user_retention_rate': self._calculate_retention_rate(period),
        }

        # Calculate job metrics
        job_metrics = {
            'total_jobs': Job.objects.count(),
            'completed_jobs': Job.objects.filter(status='completed').count(),
            'active_jobs': Job.objects.filter(status='in_progress').count(),
            'completion_rate': self._calculate_completion_rate(),
            'average_job_duration': self._calculate_average_job_duration(),
        }

        # Calculate financial metrics
        financial_metrics = {
            'total_transactions': Transaction.objects.count(),
            'total_volume': Transaction.objects.aggregate(total=Sum('amount'))['total'] or 0,
            'average_transaction': self._calculate_average_transaction(),
            'payment_method_distribution': self._get_payment_method_distribution(),
        }

        # Calculate quality metrics
        quality_metrics = {
            'average_rating': self._calculate_average_rating(),
            'rating_distribution': self._get_rating_distribution(),
            'dispute_rate': self._calculate_dispute_rate(),
            'resolution_rate': self._calculate_resolution_rate(),
        }

        # Calculate trends
        trends = {
            'user_growth': self._get_user_growth_trend(period),
            'job_activity': self._get_job_activity_trend(period),
            'revenue': self._get_revenue_trend(period),
        }

        return Response({
            'user_metrics': user_metrics,
            'job_metrics': job_metrics,
            'financial_metrics': financial_metrics,
            'quality_metrics': quality_metrics,
            'trends': trends,
        })

    def _calculate_growth_rate(self, model, date_field, period):
        # Implementation for calculating growth rate
        pass

    def _calculate_retention_rate(self, period):
        # Implementation for calculating retention rate
        pass

    def _calculate_completion_rate(self):
        # Implementation for calculating job completion rate
        pass

    def _calculate_average_job_duration(self):
        # Implementation for calculating average job duration
        pass

    def _calculate_average_transaction(self):
        # Implementation for calculating average transaction amount
        pass

    def _get_payment_method_distribution(self):
        # Implementation for getting payment method distribution
        pass

    def _calculate_average_rating(self):
        # Implementation for calculating average rating
        pass

    def _get_rating_distribution(self):
        # Implementation for getting rating distribution
        pass

    def _calculate_dispute_rate(self):
        # Implementation for calculating dispute rate
        pass

    def _calculate_resolution_rate(self):
        # Implementation for calculating resolution rate
        pass

    def _get_user_growth_trend(self, period):
        # Implementation for getting user growth trend
        pass

    def _get_job_activity_trend(self, period):
        # Implementation for getting job activity trend
        pass

    def _get_revenue_trend(self, period):
        # Implementation for getting revenue trend
        pass

class RecommendationManagementView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    @swagger_auto_schema(
        operation_description="Get recommendation system metrics and statistics",
        responses={
            200: openapi.Response(
                description="Recommendation system metrics",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'match_quality': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'average_score': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'score_distribution': openapi.Schema(type=openapi.TYPE_OBJECT),
                                'acceptance_rate': openapi.Schema(type=openapi.TYPE_NUMBER),
                            }
                        ),
                        'algorithm_metrics': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'skill_match_weight': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'experience_weight': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'rating_weight': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'location_weight': openapi.Schema(type=openapi.TYPE_NUMBER),
                            }
                        ),
                        'performance_metrics': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'average_response_time': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'cache_hit_rate': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'embedding_quality': openapi.Schema(type=openapi.TYPE_NUMBER),
                            }
                        ),
                    }
                )
            ),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):
        # Get match quality metrics
        match_quality = {
            'average_score': self._calculate_average_match_score(),
            'score_distribution': self._get_score_distribution(),
            'acceptance_rate': self._calculate_acceptance_rate(),
        }

        # Get algorithm metrics
        algorithm_metrics = {
            'skill_match_weight': MatchEngine.SKILL_WEIGHT,
            'experience_weight': MatchEngine.EXPERIENCE_WEIGHT,
            'rating_weight': MatchEngine.TARGET_JOB_WEIGHT,
            'location_weight': MatchEngine.LOCATION_WEIGHT,
        }

        # Get performance metrics
        performance_metrics = {
            'average_response_time': self._calculate_average_response_time(),
            'cache_hit_rate': self._calculate_cache_hit_rate(),
            'embedding_quality': self._calculate_embedding_quality(),
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
        MatchEngine.SKILL_WEIGHT = weights.get('skill_match_weight', MatchEngine.SKILL_WEIGHT)
        MatchEngine.EXPERIENCE_WEIGHT = weights.get('experience_weight', MatchEngine.EXPERIENCE_WEIGHT)
        MatchEngine.TARGET_JOB_WEIGHT = weights.get('rating_weight', MatchEngine.TARGET_JOB_WEIGHT)
        MatchEngine.LOCATION_WEIGHT = weights.get('location_weight', MatchEngine.LOCATION_WEIGHT)

        # Log the weight update
        ManagementLog.objects.create(
            admin=request.user,
            action='update_recommendation_weights',
            details=f"Updated recommendation weights: {weights}"
        )

        return Response({"message": "Recommendation weights updated successfully"})

    def _calculate_average_match_score(self):
        # Implementation for calculating average match score
        pass

    def _get_score_distribution(self):
        # Implementation for getting score distribution
        pass

    def _calculate_acceptance_rate(self):
        # Implementation for calculating acceptance rate
        pass

    def _calculate_average_response_time(self):
        # Implementation for calculating average response time
        pass

    def _calculate_cache_hit_rate(self):
        # Implementation for calculating cache hit rate
        pass

    def _calculate_embedding_quality(self):
        # Implementation for calculating embedding quality
        pass

class NotificationTemplateView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    @swagger_auto_schema(
        operation_description="Get all notification templates",
        responses={
            200: openapi.Response(
                description="List of notification templates",
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'name': openapi.Schema(type=openapi.TYPE_STRING),
                            'subject': openapi.Schema(type=openapi.TYPE_STRING),
                            'body': openapi.Schema(type=openapi.TYPE_STRING),
                            'type': openapi.Schema(type=openapi.TYPE_STRING),
                            'variables': openapi.Schema(type=openapi.TYPE_ARRAY, items=openapi.Schema(type=openapi.TYPE_STRING)),
                        }
                    )
                )
            ),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):
        templates = NotificationTemplate.objects.all()
        serializer = NotificationTemplateSerializer(templates, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Create a new notification template",
        request_body=NotificationTemplateSerializer,
        responses={
            201: NotificationTemplateSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def post(self, request):
        serializer = NotificationTemplateSerializer(data=request.data)
        if serializer.is_valid():
            template = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class NotificationMetricsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    @swagger_auto_schema(
        operation_description="Get notification delivery metrics and statistics",
        manual_parameters=[
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Start date", type=openapi.TYPE_STRING),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="End date", type=openapi.TYPE_STRING),
            openapi.Parameter('channel', openapi.IN_QUERY, description="Notification channel", type=openapi.TYPE_STRING),
        ],
        responses={
            200: openapi.Response(
                description="Notification metrics and statistics",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'total_sent': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'success_rate': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'delivery_time': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'average': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'p95': openapi.Schema(type=openapi.TYPE_NUMBER),
                                'p99': openapi.Schema(type=openapi.TYPE_NUMBER),
                            }
                        ),
                        'channel_stats': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'email': openapi.Schema(type=openapi.TYPE_OBJECT),
                                'sms': openapi.Schema(type=openapi.TYPE_OBJECT),
                            }
                        ),
                        'error_breakdown': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'delivery_failed': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'invalid_recipient': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'rate_limited': openapi.Schema(type=openapi.TYPE_INTEGER),
                            }
                        ),
                    }
                )
            ),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        channel = request.query_params.get('channel')

        logs = NotificationLog.objects.all()

        if start_date:
            logs = logs.filter(created_at__gte=start_date)
        if end_date:
            logs = logs.filter(created_at__lte=end_date)
        if channel:
            logs = logs.filter(channel=channel)

        total_sent = logs.count()
        successful = logs.filter(status='sent').count()
        success_rate = (successful / total_sent * 100) if total_sent > 0 else 0

        # Calculate delivery time statistics
        delivery_times = logs.filter(status='sent').values_list('sent_at', 'created_at')
        delivery_time_stats = self._calculate_delivery_time_stats(delivery_times)

        # Get channel-specific statistics
        channel_stats = self._get_channel_stats(logs)

        # Get error breakdown
        error_breakdown = self._get_error_breakdown(logs)

        return Response({
            'total_sent': total_sent,
            'success_rate': success_rate,
            'delivery_time': delivery_time_stats,
            'channel_stats': channel_stats,
            'error_breakdown': error_breakdown,
        })

    def _calculate_delivery_time_stats(self, delivery_times):
        if not delivery_times:
            return {'average': 0, 'p95': 0, 'p99': 0}

        times = [(sent - created).total_seconds() for sent, created in delivery_times]
        times.sort()

        return {
            'average': sum(times) / len(times),
            'p95': times[int(len(times) * 0.95)],
            'p99': times[int(len(times) * 0.99)],
        }

    def _get_channel_stats(self, logs):
        email_logs = logs.filter(channel='email')
        sms_logs = logs.filter(channel='sms')

        return {
            'email': {
                'total': email_logs.count(),
                'success_rate': (email_logs.filter(status='sent').count() / email_logs.count() * 100) if email_logs.count() > 0 else 0,
            },
            'sms': {
                'total': sms_logs.count(),
                'success_rate': (sms_logs.filter(status='sent').count() / sms_logs.count() * 100) if sms_logs.count() > 0 else 0,
            },
        }

    def _get_error_breakdown(self, logs):
        failed_logs = logs.filter(status='failed')
        
        return {
            'delivery_failed': failed_logs.filter(error_message__icontains='delivery failed').count(),
            'invalid_recipient': failed_logs.filter(error_message__icontains='invalid recipient').count(),
            'rate_limited': failed_logs.filter(error_message__icontains='rate limit').count(),
        }