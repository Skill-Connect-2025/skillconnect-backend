from django.db import models
from django.conf import settings
from core.constants import JOB_STATUS_CHOICES, JOB_APPLICATION_STATUS_CHOICES, PAYMENT_METHOD_CHOICES, JOB_REQUEST_STATUS_CHOICES
from apps.users.models import Worker
from django.contrib.auth.models import User
from django.utils import timezone

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
    has_active_dispute = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    assigned_worker = models.ForeignKey(
        Worker, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_jobs'
    )

    def __str__(self):
        return f"{self.title} - {self.client.username}"

    def update_dispute_status(self):
        """Update job's dispute status based on active disputes."""
        active_disputes = self.disputes.filter(status__in=['pending', 'in_review'])
        self.has_active_dispute = active_disputes.exists()
        self.save()

    def can_be_completed(self):
        """Check if job can be marked as completed."""
        return (
            self.status == 'in_progress' and
            not self.has_active_dispute and
            self.assigned_worker is not None
        )

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

class JobCompletion(models.Model):
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name='completion')
    client_completed = models.BooleanField(default=False)
    worker_completed = models.BooleanField(default=False)
    client_completed_at = models.DateTimeField(null=True, blank=True)
    worker_completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Completion status for {self.job.title}"

    def mark_client_completed(self):
        self.client_completed = True
        self.client_completed_at = timezone.now()
        self.save()
        if self.worker_completed:
            self.job.status = 'completed'
            self.job.save()

    def mark_worker_completed(self):
        self.worker_completed = True
        self.worker_completed_at = timezone.now()
        self.save()
        if self.client_completed:
            self.job.status = 'completed'
            self.job.save()

class Dispute(models.Model):
    DISPUTE_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_review', 'In Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ]

    DISPUTE_TYPE_CHOICES = [
        ('payment', 'Payment Issue'),
        ('quality', 'Quality of Work'),
        ('behavior', 'Behavior'),
        ('other', 'Other')
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='disputes')
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reported_disputes')
    reported_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='disputes')
    dispute_type = models.CharField(max_length=20, choices=DISPUTE_TYPE_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=DISPUTE_STATUS_CHOICES, default='pending')
    resolution = models.TextField(blank=True, null=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_disputes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Dispute #{self.id} - {self.job.title}"

    def mark_as_in_review(self):
        """Mark dispute as in review."""
        if self.status == 'pending':
            self.status = 'in_review'
            self.save()
            self.job.update_dispute_status()
            return True
        return False

    def mark_as_resolved(self, admin_user, resolution):
        """Mark dispute as resolved with resolution message."""
        if self.status in ['pending', 'in_review']:
            self.status = 'resolved'
            self.resolution = resolution
            self.resolved_by = admin_user
            self.resolved_at = timezone.now()
            self.save()
            self.job.update_dispute_status()
            return True
        return False

    def mark_as_closed(self):
        """Mark dispute as closed."""
        if self.status == 'resolved':
            self.status = 'closed'
            self.save()
            return True
        return False

    def notify_parties(self, subject, message):
        """Send notifications to both parties."""
        from apps.jobs.utils import send_notification
        
        # Notify reporter
        send_notification(
            self.reported_by,
            subject,
            message,
            message
        )
        
        # Notify reported user
        send_notification(
            self.reported_user,
            subject,
            message,
            message
        )