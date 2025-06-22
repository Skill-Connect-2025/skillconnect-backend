from django.db import models
from django.conf import settings
from apps.jobs.models import Job, Category
from apps.users.models import Worker
import json

class SkillSynonym(models.Model):
    """Stores synonyms for skills to enhance matching."""
    skill = models.CharField(max_length=100, unique=True)
    synonyms = models.JSONField(default=list)  
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Skill Synonyms'

    def __str__(self):
        return f"{self.skill}: {self.synonyms}"

class Location(models.Model):
    """Stores location hierarchy for matching."""
    name = models.CharField(max_length=100, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Locations'

    def __str__(self):
        return self.name

class WeightConfig(models.Model):
    """Stores category-specific matching weights."""
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True)
    skill_weight = models.FloatField(default=0.45)
    target_job_weight = models.FloatField(default=0.2)
    experience_weight = models.FloatField(default=0.2)
    education_weight = models.FloatField(default=0.05)
    location_weight = models.FloatField(default=0.1)
    rating_weight = models.FloatField(default=0.1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Weight Configurations'

    def __str__(self):
        return f"Weights for {self.category or 'Default'}"

class Embedding(models.Model):
    """Store embeddings for jobs and workers."""
    ENTITY_TYPES = [
        ('job', 'Job'),
        ('worker', 'Worker'),
    ]
    entity_type = models.CharField(max_length=10, choices=ENTITY_TYPES)
    entity_id = models.PositiveIntegerField()
    vector = models.JSONField(default=dict)  # Store raw text and keywords
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('entity_type', 'entity_id')
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
        ]

    def __str__(self):
        return f"{self.entity_type} {self.entity_id}"

class MatchResult(models.Model):
    """Store matching results between jobs and workers."""
    job = models.ForeignKey(Job, on_delete=models.CASCADE)
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)
    score = models.FloatField()
    criteria = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('job', 'worker')
        indexes = [
            models.Index(fields=['job', 'worker']),
            models.Index(fields=['score']),
        ]

    def __str__(self):
        return f"Match: Job {self.job.id} - Worker {self.worker.id} ({self.score})"