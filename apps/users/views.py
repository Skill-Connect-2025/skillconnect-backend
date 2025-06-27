from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import (
    SelectSignupMethodSerializer, SignupRequestSerializer, VerifyAndCompleteSerializer,
    LoginSerializer, PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    ClientProfileSerializer, UserSerializer, WorkerProfileSerializer, FeedbackSerializer
)
from apps.jobs.models import Job, JobApplication
from apps.jobs.serializers import JobApplicationSerializer, JobSerializer
from core.utils import IsWorker, IsClient
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from .permissions import RoleBasedPermission
from .models import VerificationToken, Worker
from django.utils import timezone
from twilio.rest import Client as TwilioClient 
from django.conf import settings
import random
import logging
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q

User = get_user_model()
logger = logging.getLogger('django')

class AuthLoginView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        request_body=LoginSerializer,
        responses={
            200: openapi.Response(
                description='Login successful',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'token': openapi.Schema(type=openapi.TYPE_STRING),
                        'user': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'username': openapi.Schema(type=openapi.TYPE_STRING),
                                'first_name': openapi.Schema(type=openapi.TYPE_STRING),
                                'last_name': openapi.Schema(type=openapi.TYPE_STRING),
                                'role': openapi.Schema(type=openapi.TYPE_STRING),
                                'email': openapi.Schema(type=openapi.TYPE_STRING),
                                'phone_number': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(
                description='Bad Request',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'non_field_errors': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(type=openapi.TYPE_STRING)
                        )
                    }
                )
            )
        }
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            try:
                user = serializer.save()
                token, created = Token.objects.get_or_create(user=user)
                if hasattr(user, 'worker'):
                    user.worker.last_activity = timezone.now()
                    user.worker.save()
                return Response({
                    "token": token.key,
                    "user": UserSerializer(user).data
                }, status=status.HTTP_200_OK)
            except Exception as e:
                return Response(
                    {"error": str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AuthSignupInitiateView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        request_body=SelectSignupMethodSerializer,
        responses={
            200: openapi.Response(
                description='Signup method selected',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'user_id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'message': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: openapi.Response(
                description='Bad Request',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'signup_method': openapi.Schema(
                            type=openapi.TYPE_ARRAY,
                            items=openapi.Schema(type=openapi.TYPE_STRING)
                        )
                    }
                )
            )
        }
    )
    def post(self, request):
        serializer = SelectSignupMethodSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"user_id": user.id, "message": "Signup method selected"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AuthSignupRequestCodeView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        request_body=SignupRequestSerializer,
        responses={
            200: openapi.Response(
                description='Verification code sent or resent',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: openapi.Response(
                description='Bad Request',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            )
        }
    )
    def post(self, request):
        serializer = SignupRequestSerializer(data=request.data)
        if serializer.is_valid():
            identifier = serializer.validated_data['identifier']
            user = serializer.validated_data['user']
            logger.info(f"Requesting verification code for user {user.id}: {identifier}")
            serializer.save()
            return Response({"message": "Verification code sent or resent"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AuthSignupCompleteView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        request_body=VerifyAndCompleteSerializer,
        responses={
            201: openapi.Response(
                description='Registration completed',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'token': openapi.Schema(type=openapi.TYPE_STRING),
                        'user': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                'username': openapi.Schema(type=openapi.TYPE_STRING),
                                'first_name': openapi.Schema(type=openapi.TYPE_STRING),
                                'last_name': openapi.Schema(type=openapi.TYPE_STRING),
                                'role': openapi.Schema(type=openapi.TYPE_STRING),
                                'email': openapi.Schema(type=openapi.TYPE_STRING),
                                'phone_number': openapi.Schema(type=openapi.TYPE_STRING),
                            }
                        )
                    }
                )
            ),
            400: openapi.Response(
                description='Bad Request',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            )
        }
    )
    def post(self, request):
        serializer = VerifyAndCompleteSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response(
                {"token": token.key, "user": UserSerializer(user).data},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AuthPasswordResetView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        request_body=PasswordResetRequestSerializer,
        responses={
            200: openapi.Response(
                description='Password reset code sent',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: openapi.Response(
                description='Bad Request',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'identifier': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            )
        }
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password reset code sent"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AuthPasswordResetConfirmView(APIView):
    permission_classes = []

    @swagger_auto_schema(
        request_body=PasswordResetConfirmSerializer,
        responses={
            200: openapi.Response(
                description='Password reset successful',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'message': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: openapi.Response(
                description='Bad Request',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'error': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            )
        }
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Password reset successful"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated, RoleBasedPermission]
    required_role = None

    @swagger_auto_schema(
        responses={
            200: openapi.Response(
                description='User profile',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'username': openapi.Schema(type=openapi.TYPE_STRING),
                        'first_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'last_name': openapi.Schema(type=openapi.TYPE_STRING),
                        'role': openapi.Schema(type=openapi.TYPE_STRING),
                        'email': openapi.Schema(type=openapi.TYPE_STRING),
                        'phone_number': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            401: openapi.Response(
                description='Unauthorized',
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'detail': openapi.Schema(type=openapi.TYPE_STRING)})
            )
        }
    )
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

class UserProfileClientView(APIView):
    permission_classes = [permissions.IsAuthenticated, RoleBasedPermission]
    required_role = 'client'

    @swagger_auto_schema(
        request_body=ClientProfileSerializer,
        responses={
            200: ClientProfileSerializer,
            400: openapi.Response(
                description='Bad Request',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'error': openapi.Schema(type=openapi.TYPE_STRING)}
                )
            ),
            401: openapi.Response(
                description='Unauthorized',
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'detail': openapi.Schema(type=openapi.TYPE_STRING)})
            ),
            403: openapi.Response(
                description='Forbidden',
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'error': openapi.Schema(type=openapi.TYPE_STRING)})
            )
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

class UserProfileWorkerView(APIView):
    permission_classes = [permissions.IsAuthenticated, RoleBasedPermission]
    required_role = 'worker'

    @swagger_auto_schema(
        responses={
            200: WorkerProfileSerializer,
            401: openapi.Response(
                description='Unauthorized',
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'detail': openapi.Schema(type=openapi.TYPE_STRING)})
            ),
            403: openapi.Response(
                description='Forbidden',
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'error': openapi.Schema(type=openapi.TYPE_STRING)})
            )
        }
    )
    def get(self, request):
        if not hasattr(request.user, 'worker'):
            return Response({"error": "User is not a worker"}, status=status.HTTP_403_FORBIDDEN)
        worker = request.user.worker
        serializer = WorkerProfileSerializer(worker, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @swagger_auto_schema(
        request_body=WorkerProfileSerializer,
        responses={
            200: WorkerProfileSerializer,
            400: openapi.Response(
                description='Bad Request',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={'error': openapi.Schema(type=openapi.TYPE_STRING)}
                )
            ),
            401: openapi.Response(
                description='Unauthorized',
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'detail': openapi.Schema(type=openapi.TYPE_STRING)})
            ),
            403: openapi.Response(
                description='Forbidden',
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'error': openapi.Schema(type=openapi.TYPE_STRING)})
            )
        }
    )
    def put(self, request):
        if not hasattr(request.user, 'worker'):
            return Response({"error": "User is not a worker"}, status=status.HTTP_403_FORBIDDEN)
        worker = request.user.worker
        serializer = WorkerProfileSerializer(
            instance=worker,
            data=request.data,
            context={'request': request},
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            worker.last_activity = timezone.now()
            worker.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class UserApplicationsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="List all applications submitted by the worker.",
        responses={
            200: openapi.Response(
                description='List of applications',
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'job': openapi.Schema(type=openapi.TYPE_OBJECT),
                            'worker': openapi.Schema(type=openapi.TYPE_OBJECT),
                            'status': openapi.Schema(type=openapi.TYPE_STRING),
                            'applied_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time')
                        }
                    )
                )
            ),
            401: openapi.Response(
                description='Unauthorized',
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'detail': openapi.Schema(type=openapi.TYPE_STRING)})
            ),
            403: openapi.Response(
                description='Forbidden',
                schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={'detail': openapi.Schema(type=openapi.TYPE_STRING)})
            )
        }
    )
    def get(self, request):
        applications = JobApplication.objects.filter(worker=request.user.worker)
        serializer = JobApplicationSerializer(applications, many=True)
        return Response(serializer.data)

class UserRatingStatsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get rating statistics for a user (worker or client).",
        responses={
            200: openapi.Response(
                description='Rating statistics',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'average_rating': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'total_ratings': openapi.Schema(type=openapi.TYPE_INTEGER),
                        'rating_breakdown': openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                '5_star': openapi.Schema(type=openapi.TYPE_NUMBER),
                                '4_star': openapi.Schema(type=openapi.TYPE_NUMBER),
                                '3_star': openapi.Schema(type=openapi.TYPE_NUMBER),
                                '2_star': openapi.Schema(type=openapi.TYPE_NUMBER),
                                '1_star': openapi.Schema(type=openapi.TYPE_NUMBER),
                            }
                        )
                    }
                )
            ),
            401: 'Unauthorized',
            404: 'Not Found'
        }
    )
    def get(self, request, user_id=None):
        try:
            # If no user_id provided, return stats for the authenticated user
            if user_id is None:
                user = request.user
            else:
                user = User.objects.get(id=user_id)
            
            stats = user.get_rating_stats()
            return Response(stats, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

class UserReviewsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get all reviews for a user (worker or client).",
        responses={
            200: openapi.Response(
                description='List of reviews',
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'job': openapi.Schema(type=openapi.TYPE_OBJECT),
                            'rating': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'review': openapi.Schema(type=openapi.TYPE_STRING),
                            'created_at': openapi.Schema(type=openapi.TYPE_STRING),
                            'reviewer': openapi.Schema(type=openapi.TYPE_OBJECT),
                        }
                    )
                )
            ),
            401: 'Unauthorized',
            404: 'Not Found'
        }
    )
    def get(self, request, user_id=None):
        try:
            if user_id is None:
                user = request.user
            else:
                user = User.objects.get(id=user_id)
            
            reviews = []
            if user.is_worker:
                # Get feedback from clients
                reviews.extend(user.worker.feedback.all())
                # Get feedback from workers (as client)
                reviews.extend(user.received_feedback.all())
            elif user.is_client:
                # Get feedback from workers
                reviews.extend(user.received_feedback.all())
            
            serializer = FeedbackSerializer(reviews, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

class RecentReviewsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get recent reviews for a user (worker or client).",
        responses={
            200: openapi.Response(
                description='List of recent reviews',
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'job': openapi.Schema(type=openapi.TYPE_OBJECT),
                            'rating': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'review': openapi.Schema(type=openapi.TYPE_STRING),
                            'created_at': openapi.Schema(type=openapi.TYPE_STRING),
                            'reviewer': openapi.Schema(type=openapi.TYPE_OBJECT),
                        }
                    )
                )
            ),
            401: 'Unauthorized',
            404: 'Not Found'
        }
    )
    def get(self, request, user_id=None):
        try:
            if user_id is None:
                user = request.user
            else:
                user = User.objects.get(id=user_id)
            
            reviews = []
            if user.is_worker:
                # Get feedback from clients
                reviews.extend(user.worker.feedback.all())
                # Get feedback from workers (as client)
                reviews.extend(user.received_feedback.all())
            elif user.is_client:
                # Get feedback from workers
                reviews.extend(user.received_feedback.all())
            
            # Sort by created_at and limit to 5 most recent
            reviews = sorted(reviews, key=lambda x: x.created_at, reverse=True)[:5]
            
            serializer = FeedbackSerializer(reviews, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

class PaymentPreferenceView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        operation_description="Get or update payment method preference",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'payment_method': openapi.Schema(
                    type=openapi.TYPE_STRING,
                    enum=['cash', 'chapa'],
                    description='Preferred payment method'
                )
            }
        ),
        responses={
            200: openapi.Response(
                description='Payment preference updated',
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        'payment_method': openapi.Schema(type=openapi.TYPE_STRING)
                    }
                )
            ),
            400: 'Bad Request',
            401: 'Unauthorized'
        }
    )
    def put(self, request):
        payment_method = request.data.get('payment_method')
        if payment_method not in ['cash', 'chapa']:
            return Response(
                {"error": "Invalid payment method. Must be 'cash' or 'chapa'"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.user.is_client:
            request.user.client.payment_method_preference = payment_method
            request.user.client.save()
        elif request.user.is_worker:
            request.user.worker.payment_method_preference = payment_method
            request.user.worker.save()
        else:
            return Response(
                {"error": "User must be either client or worker"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"payment_method": payment_method})

    def get(self, request):
        if request.user.is_client:
            preference = request.user.client.payment_method_preference
        elif request.user.is_worker:
            preference = request.user.worker.payment_method_preference
        else:
            return Response(
                {"error": "User must be either client or worker"},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"payment_method": preference})

class WorkersByPaymentMethodView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    @swagger_auto_schema(
        operation_description="Get workers filtered by payment method preference",
        responses={
            200: openapi.Response(
                description='List of workers with matching payment preference',
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'user': openapi.Schema(
                                type=openapi.TYPE_OBJECT,
                                properties={
                                    'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                                    'username': openapi.Schema(type=openapi.TYPE_STRING),
                                    'first_name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'last_name': openapi.Schema(type=openapi.TYPE_STRING),
                                    'email': openapi.Schema(type=openapi.TYPE_STRING),
                                    'phone_number': openapi.Schema(type=openapi.TYPE_STRING)
                                }
                            ),
                            'profile_pic': openapi.Schema(type=openapi.TYPE_STRING, format='uri'),
                            'location': openapi.Schema(type=openapi.TYPE_STRING),
                            'payment_method_preference': openapi.Schema(type=openapi.TYPE_STRING)
                        }
                    )
                )
            ),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):
        client_preference = request.user.client.payment_method_preference
        workers = Worker.objects.filter(payment_method_preference=client_preference)
        serializer = WorkerProfileSerializer(workers, many=True, context={'request': request})
        return Response(serializer.data)

class JobsByPaymentMethodView(APIView):
    permission_classes = [IsAuthenticated, IsWorker]

    @swagger_auto_schema(
        operation_description="Get jobs filtered by payment method preference",
        responses={
            200: openapi.Response(
                description='List of jobs with matching payment preference',
                schema=openapi.Schema(
                    type=openapi.TYPE_ARRAY,
                    items=openapi.Schema(
                        type=openapi.TYPE_OBJECT,
                        properties={
                            'id': openapi.Schema(type=openapi.TYPE_INTEGER),
                            'title': openapi.Schema(type=openapi.TYPE_STRING),
                            'location': openapi.Schema(type=openapi.TYPE_STRING),
                            'skills': openapi.Schema(type=openapi.TYPE_STRING),
                            'description': openapi.Schema(type=openapi.TYPE_STRING),
                            'payment_method': openapi.Schema(type=openapi.TYPE_STRING),
                            'status': openapi.Schema(type=openapi.TYPE_STRING),
                            'created_at': openapi.Schema(type=openapi.TYPE_STRING, format='date-time')
                        }
                    )
                )
            ),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def get(self, request):
        worker_preference = request.user.worker.payment_method_preference
        jobs = Job.objects.filter(
            status='open',
            client__payment_method_preference=worker_preference
        )
        serializer = JobSerializer(jobs, many=True)
        return Response(serializer.data)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            request.user.auth_token.delete()
        except (AttributeError, Token.DoesNotExist):
            pass
        return Response({"detail": "Successfully logged out."})