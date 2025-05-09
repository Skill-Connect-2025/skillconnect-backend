from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Client, Worker

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=['client', 'worker'], write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'phone_number', 'role']
        read_only_fields = ['id']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['role'] = 'client' if instance.is_client else 'worker' if instance.is_worker else 'admin'
        if instance.is_worker:
            data['location'] = instance.worker.location
        return data

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(
        help_text="Email or phone number to identify the user."
    )
    password = serializers.CharField(
        write_only=True,
        help_text="User's password."
    )

class UserRegistrationSerializer(UserSerializer):
    password = serializers.CharField(
        write_only=True,
        help_text="User's password."
    )

    class Meta(UserSerializer.Meta):
        fields = ['id', 'username', 'email', 'password', 'phone_number', 'role']

    def validate(self, data):
        email = data.get('email')
        phone_number = data.get('phone_number')

        if not email and not phone_number:
            raise serializers.ValidationError(
                "At least one of email or phone_number must be provided."
            )

        if email and User.objects.filter(email=email).exclude(id=self.instance.id if self.instance else None).exists():
            raise serializers.ValidationError({"email": "This email is already in use."})

        if phone_number and User.objects.filter(phone_number=phone_number).exclude(id=self.instance.id if self.instance else None).exists():
            raise serializers.ValidationError({"phone_number": "This phone number is already in use."})

        return data

    def create(self, validated_data):
        role = validated_data.pop('role')
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            phone_number=validated_data.get('phone_number', '')
        )

        if role == 'client':
            Client.objects.create(user=user)
        elif role == 'worker':
            Worker.objects.create(user=user)

        return user

class ProfileUpdateSerializer(serializers.ModelSerializer):
    location = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True,
        help_text="Location (applies to Workers only)."
    )

    class Meta:
        model = User
        fields = ['email', 'phone_number', 'location']

    def validate(self, data):
        email = data.get('email', self.instance.email)
        phone_number = data.get('phone_number', self.instance.phone_number)

        if not email and not phone_number:
            raise serializers.ValidationError(
                "At least one of email or phone_number must be provided."
            )

        if email and User.objects.filter(email=email).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError({"email": "This email is already in use."})

        if phone_number and User.objects.filter(phone_number=phone_number).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError({"phone_number": "This phone number is already in use."})

        return data

    def update(self, instance, validated_data):
        # Update User fields
        instance.email = validated_data.get('email', instance.email)
        instance.phone_number = validated_data.get('phone_number', instance.phone_number)
        instance.save()

        # Update Worker-specific fields (e.g., location)
        if instance.is_worker:
            location = validated_data.get('location')
            if location is not None:
                instance.worker.location = location
                instance.worker.save()

        return instance

    def to_representation(self, instance):
        data = {
            'email': instance.email,
            'phone_number': instance.phone_number,
        }
        if instance.is_worker:
            data['location'] = instance.worker.location
        return data