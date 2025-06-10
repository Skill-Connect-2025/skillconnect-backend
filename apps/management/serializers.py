from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.users.models import Worker, Client
from apps.users.serializers import UserSerializer
from apps.jobs.models import Feedback
from django.db.models import Avg, Count

User = get_user_model()

class ManagementUserSerializer(UserSerializer):
    """Serializer for management user operations."""
    is_client = serializers.SerializerMethodField()
    is_worker = serializers.SerializerMethodField()
    rating_stats = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = [
            'id', 'username', 'email', 'phone_number', 'first_name', 'last_name',
            'is_active', 'is_client', 'is_worker', 'rating_stats'
        ]
        read_only_fields = ['id', 'is_client', 'is_worker', 'rating_stats']

    def get_is_client(self, obj):
        return hasattr(obj, 'client')

    def get_is_worker(self, obj):
        return hasattr(obj, 'worker')

    def get_rating_stats(self, obj):
        worker_ratings = Feedback.objects.filter(worker__user=obj).aggregate(
            avg_rating=Avg('rating'), total_ratings=Count('rating')
        )
        client_ratings = Feedback.objects.filter(client=obj).aggregate(
            avg_rating=Avg('rating'), total_ratings=Count('rating')
        )
        return {
            'worker': {
                'average': worker_ratings['avg_rating'] or 0,
                'count': worker_ratings['total_ratings'] or 0
            },
            'client': {
                'average': client_ratings['avg_rating'] or 0,
                'count': client_ratings['total_ratings'] or 0
            }
        }

class ManagementUserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user profiles."""
    class Meta:
        model = User
        fields = ['username', 'email', 'phone_number', 'first_name', 'last_name']
        extra_kwargs = {
            'email': {'required': False},
            'phone_number': {'required': False}
        }

    def update(self, instance, validated_data):
        # Log management action
        from .models import ManagementLog
        ManagementLog.objects.create(
            admin=self.context['request'].user,
            action='update_user',
            details=f"Updated user {instance.username}: {validated_data}"
        )
        return super().update(instance, validated_data)