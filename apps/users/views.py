from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .serializers import UserSerializer, LoginSerializer, ProfileUpdateSerializer, UserRegistrationSerializer, CompleteProfileSerializer
from .permissions import RoleBasedPermission

User = get_user_model()

class RegisterView(APIView):
    permission_classes = []  # Public endpoint

    @swagger_auto_schema(
        request_body=UserRegistrationSerializer,
        responses={
            201: openapi.Response('User registered successfully', UserSerializer),
            400: 'Bad Request'
        }
    )
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            return Response(
                {'token': token.key, 'user': serializer.data},
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
                properties={
                    'token': openapi.Schema(type=openapi.TYPE_STRING)
                }
            )),
            401: 'Unauthorized',
            403: 'Forbidden'
        }
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            identifier = serializer.validated_data['identifier']
            password = serializer.validated_data['password']

            user = User.get_by_identifier(identifier)
            if not user:
                return Response(
                    {'error': 'Invalid email or phone number'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            user = authenticate(username=user.username, password=password)
            if user:
                if user.is_superuser:
                    return Response(
                        {'error': 'Admins cannot log in via this endpoint'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                token, created = Token.objects.get_or_create(user=user)
                return Response({'token': token.key}, status=status.HTTP_200_OK)
            return Response(
                {'error': 'Invalid password'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated, RoleBasedPermission]  # Add IsAuthenticated
    required_role = None  # Accessible to both Clients and Workers

    @swagger_auto_schema(
        responses={
            200: UserSerializer,
            401: 'Unauthorized'
        }
    )
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

class ProfileUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated, RoleBasedPermission]  # Add IsAuthenticated
    required_role = None  # Accessible to both Clients and Workers

    @swagger_auto_schema(
        request_body=ProfileUpdateSerializer,
        responses={
            200: ProfileUpdateSerializer,
            400: 'Bad Request',
            401: 'Unauthorized'
        }
    )
    def put(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CompleteProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated, RoleBasedPermission] 
    required_role = None 

    @swagger_auto_schema(
        request_body=CompleteProfileSerializer,
        responses={
            200: CompleteProfileSerializer,
            400: 'Bad Request',
            401: 'Unauthorized'
        }
    )
    def put(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  