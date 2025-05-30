from django.db import models
from apps.users.models import Worker
from apps.jobs.models import Job
import json

class MatchResult(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='match_results')
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='match_results')
    score = models.FloatField()  # Total score [0, 1]
    criteria = models.JSONField(default=dict)  # Store sub-scores (skills, experience, etc.)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'worker')
        ordering = ['-score', '-created_at']

    def __str__(self):
        return f"Match: Job {self.job.title} - Worker {self.worker.user.username} (Score: {self.score})"

class Embedding(models.Model):
    entity_type = models.CharField(max_length=50)  # 'job' or 'worker'
    entity_id = models.PositiveIntegerField()  # ID of Job or Worker
    vector = models.TextField()  # JSON-serialized vector
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('entity_type', 'entity_id')
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
        ]

    def __str__(self):
        return f"Embedding: {self.entity_type} {self.entity_id}"