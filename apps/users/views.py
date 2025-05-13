from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import (
    SignupRequestSerializer, VerifyAndProceedSerializer, CompleteRegistrationSerializer,
    LoginSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    ClientProfileSerializer, UserSerializer
)
from .permissions import RoleBasedPermission
from .models import VerificationToken
from django.utils import timezone
from twilio.rest import Client
from django.conf import settings
import random

class SignupRequestView(APIView):
    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        request_body=SignupRequestSerializer,
        responses={
            200: openapi.Response('Verification code sent'),
            400: 'Bad Request'
        }
    )
    def post(self, request):
        serializer = SignupRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Verification code sent"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class VerifyAndProceedView(APIView):
    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        request_body=VerifyAndProceedSerializer,
        responses={
            200: openapi.Response('Verification successful'),
            400: 'Bad Request'
        }
    )
    def post(self, request):
        serializer = VerifyAndProceedSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "Verification successful", "identifier": user.email or user.phone_number}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GetCodeAgainView(APIView):
    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        request_body=SignupRequestSerializer,
        responses={
            200: openapi.Response('Verification code resent'),
            400: 'Bad Request'
        }
    )
    def post(self, request):
        serializer = SignupRequestSerializer(data=request.data)
        if serializer.is_valid():
            identifier = serializer.validated_data['identifier']
            signup_method = serializer.validated_data['signup_method']
            user = User.objects.filter(email=identifier).first() if signup_method == 'email' else User.objects.filter(phone_number=identifier).first()
            if not user or user.is_verified:
                return Response({"error": "User not found or already verified"}, status=status.HTTP_400_BAD_REQUEST)
            
            code = str(random.randint(100000, 999999))
            VerificationToken.objects.create(user=user, code=code, purpose='registration')

            if signup_method == 'email':
                subject = "SkillConnect Verification Code"
                message = f"Your new verification code is: {code}\nThis code expires in 10 minutes."
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [identifier],
                    fail_silently=False,
                )
            else:
                twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
                message = f"Your new SkillConnect verification code is: {code}"
                twilio_client.messages.create(
                    body=message,
                    from_=settings.TWILIO_PHONE_NUMBER,
                    to=identifier
                )

            return Response({"message": "Verification code resent"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CompleteRegistrationView(APIView):
    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        request_body=CompleteRegistrationSerializer,
        responses={
            201: openapi.Response('Registration completed', UserSerializer),
            400: 'Bad Request'
        }
    )
    def post(self, request):
        serializer = CompleteRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response(
                {"token": token.key, "user": UserSerializer(user).data},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(APIView):
    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={
            200: openapi.Response('Login successful', openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={'token': openapi.Schema(type=openapi.TYPE_STRING)}
            )),
            400: 'Bad Request'
        }
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response({"token": token.key}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetRequestView(APIView):
    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        request_body=PasswordResetRequestSerializer,
        responses={
            200: openapi.Response('Password reset code sent'),
            400: 'Bad Request'
        }
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password reset code sent"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        request_body=PasswordResetConfirmSerializer,
        responses={
            200: openapi.Response('Password reset successful'),
            400: 'Bad Request'
        }
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password reset successful"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ClientProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated, RoleBasedPermission]
    required_role = 'client'

    @swagger_auto_schema(
        request_body=ClientProfileSerializer,
        responses={
            200: ClientProfileSerializer,
            400: 'Bad Request',
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def put(self, request):
        if not hasattr(request.user, 'client'):
            return Response({"error": "Not a client"}, status=status.HTTP_403_FORBIDDEN)
        serializer = ClientProfileSerializer(request.user.client, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated, RoleBasedPermission]
    required_role = None

    @swagger_auto_schema(
        responses={
            200: UserSerializer,
            401: 'Unauthorized'
        }
    )
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)