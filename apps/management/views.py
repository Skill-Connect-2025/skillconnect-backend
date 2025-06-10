from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .permissions import IsSuperuser
from django.contrib.auth import get_user_model
from .serializers import ManagementUserSerializer, ManagementUserUpdateSerializer
from .models import ManagementLog
from apps.jobs.utils import send_notification
import logging

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
            from apps.users.utils import generate_reset_code
            reset_code = generate_reset_code()
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