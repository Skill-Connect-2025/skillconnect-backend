from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'user_type', 'phone_number']
        read_only_fields = ['id']

    def validate(self, data):
        email = data.get('email')
        phone_number = data.get('phone_number')

        # Ensure at least one of email or phone_number is provided
        if not email and not phone_number:
            raise serializers.ValidationError(
                "At least one of email or phone_number must be provided."
            )

        # If email is provided, check uniqueness
        if email:
            if User.objects.filter(email=email).exclude(id=self.instance.id if self.instance else None).exists():
                raise serializers.ValidationError({"email": "This email is already in use."})

        # If phone_number is provided, check uniqueness
        if phone_number:
            if User.objects.filter(phone_number=phone_number).exclude(id=self.instance.id if self.instance else None).exists():
                raise serializers.ValidationError({"phone_number": "This phone number is already in use."})

        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
            user_type=validated_data['user_type'],
            phone_number=validated_data.get('phone_number', '')
        )
        return user

class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()  # Email or phone number
    password = serializers.CharField(write_only=True)