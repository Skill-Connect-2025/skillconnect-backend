from django.db import models
from django.conf import settings
from core.constants import JOB_STATUS_CHOICES, JOB_APPLICATION_STATUS_CHOICES, PAYMENT_METHOD_CHOICES, JOB_REQUEST_STATUS_CHOICES
from apps.users.models import Worker
from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Job(models.Model):
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='jobs')
    title = models.CharField(max_length=200)
    location = models.CharField(max_length=200)
    skills = models.CharField(max_length=500)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=JOB_STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_worker = models.ForeignKey(
        Worker, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_jobs'
    )

    def __str__(self):
        return f"{self.title} ({self.status})"

class JobImage(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='job_images/')

    def __str__(self):
        return f"Image for {self.job.title}"

class JobApplication(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=20, choices=JOB_STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'worker')

    def __str__(self):
        return f"{self.worker.user.username} applied to {self.job.title}"

class ClientFeedback(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='client_feedback')
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='client_feedback')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_feedback')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])  # 1 to 5 stars
    review = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'worker', 'client')

    def __str__(self):
        return f"Feedback for {self.client.username} on {self.job.title} ({self.rating}/5)"

class JobRequest(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='requests')
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='job_requests')
    status = models.CharField(max_length=20, choices=JOB_REQUEST_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'worker')

    def __str__(self):
        return f"Request for {self.worker.user.username} on {self.job.title}"

class PaymentRequest(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='payment_request')
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment request for {self.job.title} by {self.worker.user.username}"

class Feedback(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='feedback')
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='feedback')
    client = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='feedback')
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])  # 1 to 5 stars
    review = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('job', 'worker', 'client')

    def __str__(self):
        return f"Feedback for {self.worker.user.username} on {self.job.title} ({self.rating}/5)"

class Transaction(models.Model):
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='transactions')
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_transactions'
    )
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name='worker_transactions'
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='ETB')
    tx_ref = models.CharField(max_length=100, unique=True)
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    payment_method = models.CharField(
        max_length=50,
        choices=[('cash', 'Cash'), ('chapa', 'Chapa')]
    )
    status = models.CharField(
        max_length=50,
        choices=[
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('failed', 'Failed')
        ],
        default='pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Transaction {self.tx_ref} for Job {self.job.title}"