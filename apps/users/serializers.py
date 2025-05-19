from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from django.utils import timezone
from .models import Client, Worker, VerificationToken, Education, Skill, TargetJob

User = get_user_model()

class SelectSignupMethodSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=255)
    method = serializers.ChoiceField(choices=['email', 'phone'])

    def validate(self, data):
        identifier = data.get('identifier')
        method = data.get('method')

        if method == 'email':
            if '@' not in identifier or '.' not in identifier:
                raise serializers.ValidationError("Invalid email format.")
        elif method == 'phone':
            if not identifier.startswith('+') or not identifier[1:].isdigit():
                raise serializers.ValidationError("Invalid phone number format. Use + followed by digits.")

        user = User.get_by_identifier(identifier)
        if user:
            raise serializers.ValidationError({"identifier": "User with this identifier already exists."})

        return data

    def save(self):
        identifier = self.validated_data['identifier']
        method = self.validated_data['method']
        user = User.objects.create(
            email=identifier if method == 'email' else None,
            phone_number=identifier if method == 'phone' else None,
            signup_method=method
        )
        return user

class SignupRequestSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    identifier = serializers.CharField(max_length=255)

    def validate(self, data):
        identifier = data.get('identifier')
        user = User.objects.filter(id=data['user_id']).first()
        if not user or user.is_verified:
            raise serializers.ValidationError({"error": "User not found or already verified."})

        if user.signup_method == 'email' and user.email != identifier:
            raise serializers.ValidationError({"identifier": "Does not match the signup identifier."})
        if user.signup_method == 'phone' and user.phone_number != identifier:
            raise serializers.ValidationError({"identifier": "Does not match the signup identifier."})

        return data

    def save(self):
        user = User.objects.get(id=self.validated_data['user_id'])
        identifier = self.validated_data['identifier']
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

class VerifyAndCompleteSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    code = serializers.CharField(max_length=6)
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, write_only=True)
    role = serializers.ChoiceField(choices=['worker', 'client'])
    first_name = serializers.CharField(max_length=30)
    last_name = serializers.CharField(max_length=150)

    def validate(self, data):
        user = User.objects.filter(id=data['user_id']).first()
        if not user:
            raise serializers.ValidationError("User not found.")
        if user.is_verified:
            raise serializers.ValidationError("User already verified.")

        token = VerificationToken.objects.filter(
            user=user, code=data['code'], purpose='registration',
            expires_at__gt=timezone.now(), is_used=False
        ).first()
        if not token:
            raise serializers.ValidationError("Invalid or expired code.")

        validate_password(data['password'], user)
        return data

    def save(self):
        user = User.objects.get(id=self.validated_data['user_id'])
        user.username = self.validated_data['username']
        user.set_password(self.validated_data['password'])
        user.first_name = self.validated_data['first_name']
        user.last_name = self.validated_data['last_name']
        user.is_verified = True
        user.save()

        token = VerificationToken.objects.get(
            user=user, code=self.validated_data['code'], purpose='registration'
        )
        token.is_used = True
        token.save()

        role = self.validated_data['role']
        if role == 'worker':
            Worker.objects.create(user=user, has_experience=False)
        else:
            Client.objects.create(user=user)

        return user

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=255)
    password = serializers.CharField(max_length=128, write_only=True)

    def validate(self, data):
        identifier = data.get('identifier')
        password = data.get('password')
        user = User.get_by_identifier(identifier)
        if user and user.check_password(password):
            if not user.is_verified:
                raise serializers.ValidationError("User is not verified.")
            return data
        raise serializers.ValidationError("Invalid credentials.")

    def save(self):
        identifier = self.validated_data['identifier']
        return User.get_by_identifier(identifier)

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
    educations = serializers.SerializerMethodField()
    skills = serializers.SerializerMethodField()
    target_jobs = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'phone_number', 'role', 'profile_pic', 'location', 'birthdate', 'nationality', 'gender', 'has_experience', 'educations', 'skills', 'target_jobs']

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

    def validate(self, data):
        try:
            birthdate = f"{data['birthdate_year']}-{data['birthdate_month']}-{data['birthdate_day']}"
            from datetime import datetime
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
        from datetime import datetime
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


    def to_representation(self, instance):
        return {
            'birthdate': instance.birthdate.isoformat() if instance.birthdate else None,
            'location': instance.location,
            'nationality': instance.nationality,
            'gender': instance.gender,
            'email': instance.user.email,
            'phone_number': instance.user.phone_number,
            'has_experience': instance.has_experience,
            'educations': EducationSerializer(instance.educations.all(), many=True).data,
            'skills': SkillSerializer(instance.skills.all(), many=True).data,
            'target_jobs': TargetJobSerializer(instance.target_jobs.all(), many=True).data,
        }