import random
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .permissions import IsSuperuser, IsAdminUser
from django.contrib.auth import get_user_model
from .serializers import ManagementUserSerializer, ManagementUserUpdateSerializer
from .models import ManagementLog, NotificationLog, SystemAnalytics
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