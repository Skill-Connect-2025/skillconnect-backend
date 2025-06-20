from rest_framework import serializers
from apps.users.serializers import WorkerProfileSerializer
from apps.jobs.serializers import JobSerializer
from .models import MatchResult

class MatchResultSerializer(serializers.ModelSerializer):
    worker = WorkerProfileSerializer(read_only=True)
    job = JobSerializer(read_only=True)
    criteria = serializers.JSONField(read_only=True)

    class Meta:
        model = MatchResult
        fields = ['id', 'job', 'worker', 'score', 'criteria', 'created_at']
        read_only_fields = ['id', 'job', 'worker', 'score', 'criteria', 'created_at']