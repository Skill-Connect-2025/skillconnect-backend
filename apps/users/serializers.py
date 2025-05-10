from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Client, Worker

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    role = serializers.ChoiceField(choices=['client', 'worker'], write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'phone_number', 'role']
        read_only_fields = ['id']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['role'] = 'client' if instance.is_client else 'worker' if instance.is_worker else 'admin'
        if instance.is_worker:
            data['profile_pic'] = instance.worker.profile_pic.url if instance.worker.profile_pic else None
            data['location'] = instance.worker.location
        elif instance.is_client:
            data['profile_pic'] = instance.client.profile_pic.url if instance.client.profile_pic else None
            data['location'] = instance.client.location  # Added location for Clients
        return data

class UserRegistrationSerializer(UserSerializer):
    password = serializers.CharField(write_only=True)

    class Meta(UserSerializer.Meta):
        fields = ['id', 'username', 'first_name', 'last_name', 'email', 'password', 'phone_number', 'role']

    def validate(self, data):
        email = data.get('email')
        phone_number = data.get('phone_number')
        username = data.get('username')

        if not email and not phone_number:
            raise serializers.ValidationError("At least one of email or phone_number must be provided.")

        if username and User.objects.filter(username=username).exclude(id=self.instance.id if self.instance else None).exists():
            raise serializers.ValidationError({"username": "This username is already in use."})

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
            phone_number=validated_data.get('phone_number', ''),
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )

        if role == 'client':
            Client.objects.create(user=user)
        elif role == 'worker':
            Worker.objects.create(user=user)

        return user

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

class CompleteProfileSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=True)
    last_name = serializers.CharField(required=True)
    profile_pic = serializers.ImageField(required=False)
    location = serializers.CharField(max_length=100, required=True)  

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'profile_pic', 'location']

    def update(self, instance, validated_data):
        instance.first_name = validated_data['first_name']
        instance.last_name = validated_data['last_name']
        instance.save()

        if instance.is_client:
            client = instance.client
            if 'profile_pic' in validated_data:
                client.profile_pic = validated_data['profile_pic']
            client.location = validated_data['location']  
            client.save()

        if instance.is_worker:
            worker = instance.worker
            if 'profile_pic' in validated_data:
                worker.profile_pic = validated_data['profile_pic']
            worker.location = validated_data['location']
            worker.save()

        return instance

class ProfileUpdateSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    profile_pic = serializers.ImageField(required=False)
    location = serializers.CharField(max_length=100, required=False)
    username = serializers.CharField(required=False)  # Add username field

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone_number', 'profile_pic', 'location']  # Include username

    def validate(self, data):
        if 'email' in data or 'phone_number' in data:
            raise serializers.ValidationError("Email and phone number cannot be updated.")

        # Validate username uniqueness
        username = data.get('username')
        if username and User.objects.filter(username=username).exclude(id=self.instance.id).exists():
            raise serializers.ValidationError({"username": "This username is already in use."})

        return data

    def update(self, instance, validated_data):
        instance.username = validated_data.get('username', instance.username)  # Update username
        instance.first_name = validated_data.get('first_name', instance.first_name)
        instance.last_name = validated_data.get('last_name', instance.last_name)
        instance.save()

        if instance.is_client:
            client = instance.client
            if 'profile_pic' in validated_data:
                client.profile_pic = validated_data['profile_pic']
            if 'location' in validated_data:
                client.location = validated_data['location']
            client.save()

        if instance.is_worker:
            worker = instance.worker
            if 'profile_pic' in validated_data:
                worker.profile_pic = validated_data['profile_pic']
            if 'location' in validated_data:
                worker.location = validated_data['location']
            worker.save()

        return instance