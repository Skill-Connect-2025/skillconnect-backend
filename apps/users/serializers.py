from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Client, Worker, VerificationToken
import random
from django.core.mail import send_mail
from django.conf import settings
from twilio.rest import Client as TwilioClient
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from django.db import transaction

User = get_user_model()

class SelectSignupMethodSerializer(serializers.Serializer):
    signup_method = serializers.ChoiceField(choices=['email', 'phone'])

    def save(self):
        signup_method = self.validated_data['signup_method']
        user = User.objects.create(
            username=f"temp_{random.randint(100000, 999999)}",
            is_active=False,
            signup_method=signup_method
        )
        return user

class SignupRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    user_id = serializers.IntegerField()

    def validate(self, data):
        user = User.objects.filter(id=data['user_id'], is_active=False).first()
        if not user:
            raise serializers.ValidationError("Invalid user ID or user already active.")
        if not user.signup_method:
            raise serializers.ValidationError("Signup method not set for this user.")
        data['signup_method'] = user.signup_method
        if user.signup_method == 'email':
            if not data['identifier'] or '@' not in data['identifier']:
                raise serializers.ValidationError("Invalid email address.")
            if User.objects.filter(email=data['identifier']).exclude(id=user.id).exists():
                raise serializers.ValidationError("Email already registered.")
        else:
            if not data['identifier'].startswith('+') or len(data['identifier']) < 10:
                raise serializers.ValidationError("Invalid phone number (e.g., +251912345678).")
            if User.objects.filter(phone_number=data['identifier']).exclude(id=user.id).exists():
                raise serializers.ValidationError("Phone number already registered.")
        return data

    def save(self):
        user = User.objects.get(id=self.validated_data['user_id'])
        identifier = self.validated_data['identifier']
        signup_method = self.validated_data['signup_method']
        code = str(random.randint(100000, 999999))

        if signup_method == 'email':
            user.email = identifier
        else:
            user.phone_number = identifier
        user.save()

        VerificationToken.objects.create(user=user, code=code, purpose='registration')

        if signup_method == 'email':
            subject = "SkillConnect Verification Code"
            message = f"Your verification code is: {code}\nThis code expires in 10 minutes."
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [identifier],
                fail_silently=False,
            )
        else:
            twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)  # Fixed
            message = f"Your SkillConnect verification code is: {code}"
            twilio_client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=identifier
            )

        return user

class VerifyAndCompleteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    identifier = serializers.CharField()
    code = serializers.CharField(max_length=6)
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['client', 'worker'])

    def validate(self, data):
        user = User.objects.filter(id=data['user_id'], is_active=False).first()
        if not user:
            raise serializers.ValidationError("Invalid user ID or user already active.")
        if user.is_verified:
            raise serializers.ValidationError("User already verified.")
        if user.signup_method == 'email' and user.email != data['identifier']:
            raise serializers.ValidationError("Identifier does not match the email provided.")
        if user.signup_method == 'phone' and user.phone_number != data['identifier']:
            raise serializers.ValidationError("Identifier does not match the phone number provided.")
        token = VerificationToken.objects.filter(
            user=user, code=data['code'], purpose='registration', is_used=False, expires_at__gt=timezone.now()
        ).first()
        if not token:
            raise serializers.ValidationError("Invalid or expired verification code.")
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        validate_password(data['password'])
        return data

    def save(self):
        user = User.objects.get(id=self.validated_data['user_id'])
        with transaction.atomic():
            user.is_verified = True
            user.is_active = True
            user.first_name = self.validated_data['first_name']
            user.last_name = self.validated_data['last_name']
            user.username = f"{self.validated_data['first_name'].lower()}.{self.validated_data['last_name'].lower()}"
            user.set_password(self.validated_data['password'])
            user.save()
            VerificationToken.objects.filter(user=user, code=self.validated_data['code']).update(is_used=True)
            if self.validated_data['role'] == 'client':
                Client.objects.create(user=user)  # This should now work
            else:
                Worker.objects.create(user=user)
        return user

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = User.get_by_identifier(data['identifier'])
        if not user:
            raise serializers.ValidationError("Invalid email or phone number.")
        if not user.is_verified or not user.is_active:
            raise serializers.ValidationError("Account not verified or inactive.")
        if not user.check_password(data['password']):
            raise serializers.ValidationError("Invalid password.")
        if user.is_superuser:
            raise serializers.ValidationError("Admins cannot log in via this endpoint.")
        return data

    def save(self):
        user = User.get_by_identifier(self.validated_data['identifier'])
        return user

class PasswordResetRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField()

    def validate_identifier(self, value):
        user = User.get_by_identifier(value)
        if not user:
            raise serializers.ValidationError("No user found with this email or phone number.")
        if not user.email and not user.phone_number:
            raise serializers.ValidationError("User has no email or phone number for reset.")
        return value

    def save(self):
        identifier = self.validated_data['identifier']
        user = User.get_by_identifier(identifier)
        code = str(random.randint(100000, 999999))

        VerificationToken.objects.create(user=user, code=code, purpose='password_reset')

        if user.email:
            subject = "SkillConnect Password Reset Code"
            message = f"Your password reset code is: {code}\nThis code expires in 10 minutes."
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
        elif user.phone_number:
            twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)  # Fixed
            message = f"Your SkillConnect password reset code is: {code}"
            twilio_client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=user.phone_number
            )

class PasswordResetConfirmSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError("Passwords do not match.")
        validate_password(data['new_password'])
        user = User.get_by_identifier(data['identifier'])
        if not user:
            raise serializers.ValidationError("No user found with this identifier.")
        token = VerificationToken.objects.filter(
            user=user, code=data['code'], purpose='password_reset', is_used=False, expires_at__gt=timezone.now()
        ).first()
        if not token:
            raise serializers.ValidationError("Invalid or expired reset code.")
        return data

    def save(self):
        user = User.get_by_identifier(self.validated_data['identifier'])
        user.set_password(self.validated_data['new_password'])
        user.save()
        VerificationToken.objects.filter(user=user, code=self.validated_data['code']).update(is_used=True)

class ClientProfileSerializer(serializers.Serializer):
    profile_pic = serializers.ImageField(required=False, allow_null=True)
    location = serializers.CharField(required=True)

    def validate(self, data):
        if not data.get('location'):
            raise serializers.ValidationError("Location is required.")
        return data

    def update(self, instance, validated_data):
        instance.profile_pic = validated_data.get('profile_pic', instance.profile_pic)
        instance.location = validated_data.get('location', instance.location)
        instance.save()
        return instance

    def to_representation(self, instance):
        return {
            'profile_pic': instance.profile_pic.url if instance.profile_pic else None,
            'location': instance.location
        }

class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    profile_pic = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'phone_number', 'role', 'profile_pic', 'location']

    def get_role(self, obj):
        if obj.is_superuser:
            return 'admin'
        if obj.is_client:
            return 'client'
        if obj.is_worker:
            return 'worker'
        return None

    def get_profile_pic(self, obj):
        if obj.is_client and obj.client.profile_pic:
            return obj.client.profile_pic.url
        if obj.is_worker and obj.worker.profile_pic:
            return obj.worker.profile_pic.url
        return None

    def get_location(self, obj):
        if obj.is_client:
            return obj.client.location
        if obj.is_worker:
            return obj.worker.location
        return None