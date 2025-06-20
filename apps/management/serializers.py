from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.management.models import ManagementLog, NotificationLog, SystemAnalytics, NotificationTemplate
from apps.users.models import Worker, Client
from apps.users.serializers import UserSerializer
from apps.jobs.models import Feedback, Job, Transaction
from django.db.models import Avg, Count, Sum
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from apps.management.permissions import IsSuperuser, IsAdminUser
from apps.jobs.utils import send_notification
from apps.users.models import VerificationToken
import random
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

class ManagementUserSerializer(UserSerializer):
    """Serializer for management user operations."""
    is_client = serializers.SerializerMethodField()
    is_worker = serializers.SerializerMethodField()
    rating_stats = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = [
            'id', 'username', 'email', 'phone_number', 'first_name', 'last_name',
            'is_active', 'is_client', 'is_worker', 'rating_stats'
        ]
        read_only_fields = ['id', 'is_client', 'is_worker', 'rating_stats']

    def get_is_client(self, obj):
        return hasattr(obj, 'client')

    def get_is_worker(self, obj):
        return hasattr(obj, 'worker')

    def get_rating_stats(self, obj):
        worker_ratings = Feedback.objects.filter(worker__user=obj).aggregate(
            avg_rating=Avg('rating'), total_ratings=Count('rating')
        )
        client_ratings = Feedback.objects.filter(client=obj).aggregate(
            avg_rating=Avg('rating'), total_ratings=Count('rating')
        )
        return {
            'worker': {
                'average': worker_ratings['avg_rating'] or 0,
                'count': worker_ratings['total_ratings'] or 0
            },
            'client': {
                'average': client_ratings['avg_rating'] or 0,
                'count': client_ratings['total_ratings'] or 0
            }
        }

class ManagementUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profiles."""
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'first_name', 'last_name']
        extra_kwargs = {
            'email': {'required': False},
            'phone_number': {'required': False}
        }

    def update(self, instance, validated_data):
        # Log management action
        ManagementLog.objects.create(
            admin=self.context['request'].user,
            action='update_user',
            details=f"Updated user {instance.username}: {validated_data}"
        )
        return super().update(instance, validated_data)

class NotificationLogSerializer(serializers.ModelSerializer):
    recipient = UserSerializer(read_only=True)

    class Meta:
        model = NotificationLog
        fields = [
            'id', 'recipient', 'subject', 'message', 'channel',
            'status', 'error_message', 'sent_at', 'created_at'
        ]
        read_only_fields = ['id', 'recipient', 'status', 'error_message', 'sent_at', 'created_at']

class SystemAnalyticsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemAnalytics
        fields = [
            'date', 'total_users', 'total_clients', 'total_workers',
            'total_jobs', 'completed_jobs', 'total_transactions',
            'total_transaction_amount', 'average_rating',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']

class BroadcastNotificationSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=200)
    message = serializers.CharField()
    recipients = serializers.ChoiceField(choices=['all', 'clients', 'workers'])
    channel = serializers.ChoiceField(choices=['email', 'sms', 'both'])

    def validate(self, data):
        if data['channel'] == 'both' and not data.get('subject'):
            raise serializers.ValidationError("Subject is required for email notifications")
        return data

class ManagementLogSerializer(serializers.ModelSerializer):
    admin = UserSerializer(read_only=True)

    class Meta:
        model = ManagementLog
        fields = ['id', 'admin', 'action', 'details', 'timestamp']
        read_only_fields = ['id', 'admin', 'timestamp']

class ManagementUserResetPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsSuperuser]

    def post(self, request, user_id):
        """Generate and send a password reset code."""
        try:
            user = User.objects.get(id=user_id)
            if not user.is_active:
                return Response({"error": "Cannot reset password for inactive user"}, status=status.HTTP_400_BAD_REQUEST)
            if not (user.email or user.phone_number):
                return Response({"error": "User has no email or phone number"}, status=status.HTTP_400_BAD_REQUEST)
            # Generate and store code
            reset_code = str(random.randint(100000, 999999))
            VerificationToken.objects.create(
                user=user,
                code=reset_code,
                purpose='password_reset'
            )
            # Send notification
            identifier = user.email if user.email else user.phone_number
            if user.email:
                email_subject = "SkillConnect Password Reset Code"
                email_message = f"Your password reset code is: {reset_code}\nThis code expires in 24 hours."
                sms_message = ''
            else:
                email_subject = ''
                email_message = ''
                sms_message = f"Your SkillConnect password reset code is: {reset_code}"
            send_notification(user, identifier, email_subject, email_message, sms_message)
            # Log action
            ManagementLog.objects.create(
                admin=request.user,
                action='reset_password',
                details=f'Reset password for user {user.username} (ID: {user_id}) via {identifier}'
            )
            logger.info(f"Password reset code sent for user {user.id}: {identifier}")
            return Response({"message": "Password reset code sent"})
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ['id', 'name', 'subject', 'body', 'type', 'variables', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']

    def validate_variables(self, value):
        """Validate that variables is a list of strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Variables must be a list")
        if not all(isinstance(v, str) for v in value):
            raise serializers.ValidationError("All variables must be strings")
        return value

    def validate(self, data):
        """Validate that all required variables are present in the template."""
        subject = data.get('subject', '')
        body = data.get('body', '')
        variables = data.get('variables', [])

        # Check for variables in subject and body
        import re
        template_vars = set(re.findall(r'\{(\w+)\}', subject + body))
        required_vars = set(variables)

        if template_vars != required_vars:
            missing = required_vars - template_vars
            extra = template_vars - required_vars
            errors = []
            if missing:
                errors.append(f"Variables {missing} are required but not used in template")
            if extra:
                errors.append(f"Variables {extra} are used in template but not declared")
            raise serializers.ValidationError(errors)

        return data