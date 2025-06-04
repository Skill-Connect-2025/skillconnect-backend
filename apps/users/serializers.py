from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from django.utils import timezone
from .models import Client, Worker, VerificationToken, Education, Skill, TargetJob
from datetime import datetime
import uuid
import random
from django.core.mail import send_mail
from django.conf import settings
from twilio.rest import Client as TwilioClient
from django.contrib.auth import get_user_model
from django.core.cache import cache
from datetime import timedelta
from apps.jobs.models import Job, JobRequest, Feedback
from apps.jobs.feedback_serializers import FeedbackSerializer

import logging

User = get_user_model()
logger = logging.getLogger('django')

class SelectSignupMethodSerializer(serializers.Serializer):
    signup_method = serializers.ChoiceField(choices=['email', 'phone'])

    def validate(self, data):
        signup_method = data.get('signup_method')
        if signup_method not in ['email', 'phone']:
            raise serializers.ValidationError("Signup method must be 'email' or 'phone'.")
        return data

    def save(self):
        signup_method = self.validated_data['signup_method']
        # Generate a unique temporary username
        temp_username = f"temp_{uuid.uuid4().hex[:10]}"
        user = User.objects.create(
            username=temp_username,
            signup_method=signup_method,
            is_active=False
        )
        return user

class SignupRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    identifier = serializers.CharField(max_length=255)

    def validate(self, data):
        user_id = data.get('user_id')
        identifier = data.get('identifier').strip()
        try:
            user = User.objects.get(id=user_id, is_active=False)
        except User.DoesNotExist:
            raise serializers.ValidationError({"error": "User not found or already verified."})
        if user.signup_method == 'email':
            if '@' not in identifier or '.' not in identifier:
                raise serializers.ValidationError({"identifier": "Invalid email format."})
            if User.objects.filter(email__iexact=identifier).exclude(id=user_id).exists():
                raise serializers.ValidationError({"identifier": "Email already in use."})
        elif user.signup_method == 'phone':
            if not identifier.startswith('+') or not identifier[1:].isdigit():
                raise serializers.ValidationError({"identifier": "Invalid phone number format."})
            if User.objects.filter(phone_number=identifier).exclude(id=user_id).exists():
                raise serializers.ValidationError({"identifier": "Phone number already in use."})
        else:
            raise serializers.ValidationError({"error": "Invalid signup method."})
        data['user'] = user
        data['identifier'] = identifier
        return data

    def save(self):
        user = self.validated_data['user']
        identifier = self.validated_data['identifier']
        logger.debug(f"Storing identifier for user {user.id}: {identifier} (signup_method: {user.signup_method})")
        if user.signup_method == 'email':
            user.email = identifier
            user.phone_number = None
        else:
            user.phone_number = identifier
            user.email = user.email or 'temp@skillconnect.com'
        user.save()
        logger.info(f"Stored identifier for user {user.id}: email={user.email}, phone={user.phone_number}")
        code = str(random.randint(100000, 999999))
        VerificationToken.objects.create(user=user, code=code, purpose='registration')
        if user.signup_method == 'email':
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
            twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            message = f"Your SkillConnect verification code is: {code}"
            twilio_client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=identifier
            )
        logger.info(f"Verification code sent for user {user.id}: {identifier}")
        return user

class VerifyAndCompleteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    code = serializers.CharField(max_length=6)
    password = serializers.CharField(
        max_length=128,
        write_only=True,
        min_length=8,
        error_messages={'min_length': 'Password must be at least 8 characters long.'}
    )
    confirm_password = serializers.CharField(
        max_length=128,
        write_only=True,
        min_length=8,
        error_messages={'min_length': 'Confirm password must be at least 8 characters long.'}
    )
    role = serializers.ChoiceField(choices=['worker', 'client'])
    first_name = serializers.CharField(
        max_length=30,
        min_length=2,
        error_messages={'min_length': 'First name must be at least 2 characters long.'}
    )
    last_name = serializers.CharField(
        max_length=150,
        min_length=2,
        error_messages={'min_length': 'Last name must be at least 2 characters long.'}
    )

    def validate(self, data):
        user = User.objects.filter(id=data['user_id']).first()
        if not user:
            raise serializers.ValidationError("User not found.")
        if user.is_verified:
            raise serializers.ValidationError("User already verified.")
        if not user.email and not user.phone_number:
            logger.error(f"User {user.id} has no email or phone_number set")
            raise serializers.ValidationError("Email or phone number must be set. Please request a verification code.")
        token = VerificationToken.objects.filter(
            user=user,
            code=data['code'],
            purpose='registration',
            expires_at__gt=timezone.now(),
            is_used=False
        ).first()
        if not token:
            raise serializers.ValidationError("Invalid or expired verification code.")
        if data['password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match. Please ensure both passwords are identical."})
        try:
            validate_password(data['password'], user)
        except Exception as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        if not data['first_name'].replace(' ', '').isalpha():
            raise serializers.ValidationError({"first_name": "First name should only contain letters."})
        if not data['last_name'].replace(' ', '').isalpha():
            raise serializers.ValidationError({"last_name": "Last name should only contain letters."})
        return data

    def save(self):
        user = User.objects.get(id=self.validated_data['user_id'])
        logger.debug(f"Completing signup for user {user.id}: email={user.email}, phone={user.phone_number}")
        user.set_password(self.validated_data['password'])
        user.first_name = self.validated_data['first_name'].strip()
        user.last_name = self.validated_data['last_name'].strip()
        base_username = f"{user.first_name.lower()}.{user.last_name.lower()}"
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exclude(id=user.id).exists():
            username = f"{base_username}{counter}"
            counter += 1
        user.username = username
        user.is_verified = True
        user.is_active = True
        user.save()
        if not user.check_password(self.validated_data['password']):
            logger.error(f"Password hashing failed for user {user.id}")
            raise serializers.ValidationError("Failed to set password. Please try again.")
        token = VerificationToken.objects.get(
            user=user,
            code=self.validated_data['code'],
            purpose='registration'
        )
        token.is_used = True
        token.save()
        role = self.validated_data['role']
        if role == 'worker':
            Worker.objects.create(user=user, has_experience=False)
        else:
            Client.objects.create(user=user)
        logger.info(f"User {user.id} completed signup: email={user.email}, role={role}")
        return user

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=255, trim_whitespace=True)
    password = serializers.CharField(max_length=128, write_only=True)

    def validate(self, data):
        identifier = data.get('identifier').strip().lower()
        password = data.get('password')
        logger.debug(f"Login attempt for identifier: {identifier}")
        cache_key = f'login_attempts_{identifier}'
        attempts = cache.get(cache_key, 0)
        if attempts >= 5:
            logger.warning(f"Too many login attempts for {identifier}")
            raise serializers.ValidationError("Too many login attempts. Please try again in 15 minutes.")
        user = User.objects.filter(
            Q(email__iexact=identifier) | Q(phone_number=identifier) | Q(username__iexact=identifier)
        ).first()
        if not user:
            logger.error(f"No user found for identifier: {identifier}")
            cache.set(cache_key, attempts + 1, 900)
            raise serializers.ValidationError("No user found with this email, phone, or username.")
        if not user.check_password(password):
            logger.error(f"Password incorrect for user: {user.email or user.username}")
            cache.set(cache_key, attempts + 1, 900)
            raise serializers.ValidationError("Incorrect password.")
        if not user.is_verified:
            logger.error(f"User not verified: {user.email or user.username}")
            raise serializers.ValidationError("User is not verified. Please complete the registration process.")
        if not user.is_active:
            logger.error(f"User not active: {user.email or user.username}")
            raise serializers.ValidationError("User account is disabled. Please contact support.")
        logger.info(f"Login successful for user: {user.email or user.username}")
        cache.delete(cache_key)
        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        return user

class PasswordResetRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=255)

    def validate(self, data):
        identifier = data.get('identifier')
        user = User.get_by_identifier(identifier)
        if not user:
            raise serializers.ValidationError("User not found.")
        if not user.is_verified:
            raise serializers.ValidationError("User is not verified.")
        return data

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
                [identifier],
                fail_silently=False,
            )
        else:
            twilio_client = TwilioClient(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            message = f"Your SkillConnect password reset code is: {code}"
            twilio_client.messages.create(
                body=message,
                from_=settings.TWILIO_PHONE_NUMBER,
                to=identifier
            )

class PasswordResetConfirmSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=255)
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField(max_length=128, write_only=True)

    def validate(self, data):
        identifier = data.get('identifier')
        user = User.get_by_identifier(identifier)
        if not user:
            raise serializers.ValidationError("User not found.")

        token = VerificationToken.objects.filter(
            user=user, code=data['code'], purpose='password_reset',
            expires_at__gt=timezone.now(), is_used=False
        ).first()
        if not token:
            raise serializers.ValidationError("Invalid or expired code.")

        validate_password(data['new_password'], user)
        return data

    def save(self):
        identifier = self.validated_data['identifier']
        user = User.get_by_identifier(identifier)
        user.set_password(self.validated_data['new_password'])
        user.save()

        token = VerificationToken.objects.get(
            user=user, code=self.validated_data['code'], purpose='password_reset'
        )
        token.is_used = True
        token.save()


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    profile_pic = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    birthdate = serializers.SerializerMethodField()
    nationality = serializers.SerializerMethodField()
    gender = serializers.SerializerMethodField()
    has_experience = serializers.SerializerMethodField()
    years_of_experience = serializers.SerializerMethodField()
    educations = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()
    target_jobs = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    feedback = serializers.SerializerMethodField()
    rating_stats = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'first_name', 'last_name',
            'role', 'profile_pic', 'location', 'birthdate', 'nationality', 'gender',
            'has_experience', 'years_of_experience', 'educations', 'skills', 'target_jobs',
            'email', 'phone_number', 'feedback', 'rating_stats'
        ]

    def get_role(self, obj):
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

    def get_birthdate(self, obj):
        if obj.is_worker:
            return obj.worker.birthdate
        return None

    def get_nationality(self, obj):
        if obj.is_worker:
            return obj.worker.nationality
        return None

    def get_gender(self, obj):
        if obj.is_worker:
            return obj.worker.gender
        return None

    def get_has_experience(self, obj):
        if obj.is_worker:
            return obj.worker.has_experience
        return None

    def get_years_of_experience(self, obj):
        if obj.is_worker:
            return obj.worker.years_of_experience
        return None

    def get_educations(self, obj):
        if obj.is_worker:
            return EducationSerializer(obj.worker.educations.all(), many=True).data
        return []

    def get_skills(self, obj):
        if obj.is_worker:
            return SkillSerializer(obj.worker.skills.all(), many=True).data
        return []

    def get_target_jobs(self, obj):
        if obj.is_worker:
            return TargetJobSerializer(obj.worker.target_jobs.all(), many=True).data
        return []

    def get_email(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
            return None
        # Reveal email for workers if requester is a client with an accepted job request
        if obj.is_worker and request.user.is_client:
            job = Job.objects.filter(
                client=request.user,
                assigned_worker=obj.worker,
                status__in=['in_progress', 'completed', 'pending_payment']
            ).first()
            if job:
                return obj.email
        
        if obj == request.user:
            return obj.email
        return None

    def get_phone_number(self, obj):
        request = self.context.get('request')
        if not request or not hasattr(request, 'user') or not request.user.is_authenticated:
            return None
        
        if obj.is_worker and request.user.is_client:
            job = Job.objects.filter(
                client=request.user,
                assigned_worker=obj.worker,
                status__in=['in_progress', 'completed', 'pending_payment']
            ).first()
            if job:
                return obj.phone_number
        if obj == request.user:
            return obj.phone_number
        return None
    
    def get_feedback(self, obj):
        if obj.is_worker:
            return FeedbackSerializer(obj.worker.feedback.all(), many=True).data
        return []

    def get_rating_stats(self, obj):
        return obj.get_rating_stats()

class ClientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ['profile_pic', 'location']

class EducationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Education
        fields = ['institute_name', 'level_of_study', 'field_of_study', 'country', 'city', 'graduation_month', 'graduation_year']

class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['name', 'level']

class TargetJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = TargetJob
        fields = ['job_title', 'level', 'open_to_work']

class WorkerProfileSerializer(serializers.Serializer):
    birthdate_day = serializers.IntegerField(min_value=1, max_value=31)
    birthdate_month = serializers.CharField()
    birthdate_year = serializers.IntegerField(min_value=1900, max_value=2025)
    location = serializers.CharField(required=True)
    nationality = serializers.CharField(required=True)
    gender = serializers.CharField(required=True)
    email = serializers.EmailField(required=False, allow_null=True)
    phone_number = serializers.CharField(required=False, allow_null=True)
    has_experience = serializers.BooleanField(required=True)
    educations = EducationSerializer(many=True, required=True)
    skills = SkillSerializer(many=True, required=True)
    target_jobs = TargetJobSerializer(many=True, required=True)
    years_of_experience = serializers.FloatField(read_only=True)
    last_activity = serializers.DateTimeField(read_only=True)
    feedback = serializers.SerializerMethodField(read_only=True)
    rating_stats = serializers.SerializerMethodField(read_only=True)

    class Meta:
        ref_name = 'UsersWorkerProfile' 
    
    def get_feedback(self, obj):
        return FeedbackSerializer(obj.feedback.all(), many=True).data

    def get_rating_stats(self, obj):
        return obj.user.get_rating_stats()

    def validate(self, data):
        try:
            birthdate = f"{data['birthdate_year']}-{data['birthdate_month']}-{data['birthdate_day']}"
            datetime.strptime(birthdate, '%Y-%B-%d')
        except ValueError:
            try:
                birthdate = f"{data['birthdate_year']}-{data['birthdate_month']}-{data['birthdate_day']}"
                datetime.strptime(birthdate, '%Y-%m-%d')
            except ValueError:
                raise serializers.ValidationError("Invalid birthdate format. Use a valid month (e.g., 'May' or '05').")

        if not data.get('skills'):
            raise serializers.ValidationError("At least one skill is required.")
        if not data.get('target_jobs'):
            raise serializers.ValidationError("At least one target job is required.")
        user = self.context['request'].user
        if not user.email and not data.get('email'):
            raise serializers.ValidationError("Email is required if not set during signup.")
        if not user.phone_number and not data.get('phone_number'):
            raise serializers.ValidationError("Phone number is required if not set during signup.")
        return data

    def update(self, instance, validated_data):
        try:
            birthdate = datetime.strptime(
                f"{validated_data['birthdate_year']}-{validated_data['birthdate_month']}-{validated_data['birthdate_day']}",
                '%Y-%B-%d'
            ).date()
        except ValueError:
            birthdate = datetime.strptime(
                f"{validated_data['birthdate_year']}-{validated_data['birthdate_month']}-{validated_data['birthdate_day']}",
                '%Y-%m-%d'
            ).date()

        instance.birthdate = birthdate
        instance.location = validated_data.get('location', instance.location)
        instance.nationality = validated_data.get('nationality', instance.nationality)
        instance.gender = validated_data.get('gender', instance.gender)
        instance.has_experience = validated_data.get('has_experience', instance.has_experience)
        instance.save()

        user = instance.user
        user.email = validated_data.get('email', user.email)
        user.phone_number = validated_data.get('phone_number', user.phone_number)
        user.save()

        instance.educations.all().delete()
        for education_data in validated_data.get('educations', []):
            Education.objects.create(worker=instance, **education_data)

        instance.skills.all().delete()
        for skill_data in validated_data.get('skills', []):
            Skill.objects.create(worker=instance, **skill_data)

        instance.target_jobs.all().delete()
        for target_job_data in validated_data.get('target_jobs', []):
            TargetJob.objects.create(worker=instance, **target_job_data)

        return instance

    def to_representation(self, instance):
        return {
            'birthdate': instance.birthdate.isoformat() if instance.birthdate else None,
            'location': instance.location,
            'nationality': instance.nationality,
            'gender': instance.gender,
            'email': instance.user.email,
            'phone_number': instance.user.phone_number,
            'has_experience': instance.has_experience,
            'years_of_experience': instance.years_of_experience, 
            'educations': EducationSerializer(instance.educations.all(), many=True).data,
            'skills': SkillSerializer(instance.skills.all(), many=True).data,
            'target_jobs': TargetJobSerializer(instance.target_jobs.all(), many=True).data,
        }