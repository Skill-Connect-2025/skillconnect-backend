from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q
from .models import Client, Worker

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['client', 'worker'], write_only=True)  

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'phone_number']
        read_only_fields = ['id']

    def validate(self, data):
        email = data.get('email')
        phone_number = data.get('phone_number')

        if not email and not phone_number:
            raise serializers.ValidationError(
                "At least one of email or phone_number must be provided."
            )

        if email:
            if User.objects.filter(email=email).exclude(id=self.instance.id if self.instance else None).exists():
                raise serializers.ValidationError({"email": "This email is already in use."})

        if phone_number:
            if User.objects.filter(phone_number=phone_number).exclude(id=self.instance.id if self.instance else None).exists():
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

        # Create Client or Worker instance based on role
        if role == 'client':
            Client.objects.create(user=user)
        elif role == 'worker':
            Worker.objects.create(user=user)

        return user

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['role'] = 'client' if instance.is_client else 'worker' if instance.is_worker else 'admin'
        return data

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)