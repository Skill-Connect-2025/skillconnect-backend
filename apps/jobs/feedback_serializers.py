from rest_framework import serializers
from .models import Feedback

class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['id', 'job', 'worker', 'client', 'rating', 'review', 'created_at']
        read_only_fields = ['worker', 'client', 'created_at']

    def validate(self, data):
        job = data['job']
        client = self.context['request'].user
        if job.status != 'completed':
            raise serializers.ValidationError("Cannot submit feedback for a non-completed job.")
        if job.client != client:
            raise serializers.ValidationError("Only the job's client can submit feedback.")
        if Feedback.objects.filter(job=job).exists():
            raise serializers.ValidationError("Feedback already submitted for this job.")
        return data