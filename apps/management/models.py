from django.db import models
from django.conf import settings
from django.utils import timezone

class ManagementLog(models.Model):
    """Log management actions (e.g., user suspension, password reset)."""
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    action = models.CharField(max_length=100)
    details = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.admin.username} - {self.action} at {self.timestamp}"

class NotificationLog(models.Model):
    """Track system notifications sent to users."""
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('both', 'Both')
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed')
    ]

    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification to {self.recipient.username} - {self.status}"

    def mark_as_sent(self):
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()

    def mark_as_failed(self, error_message):
        self.status = 'failed'
        self.error_message = error_message
        self.save()

class SystemAnalytics(models.Model):
    """Store system-wide analytics data."""
    date = models.DateField(unique=True)
    total_users = models.IntegerField(default=0)
    total_clients = models.IntegerField(default=0)
    total_workers = models.IntegerField(default=0)
    total_jobs = models.IntegerField(default=0)
    completed_jobs = models.IntegerField(default=0)
    total_transactions = models.IntegerField(default=0)
    total_transaction_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    average_rating = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'System Analytics'

    def __str__(self):
        return f"Analytics for {self.date}"

class NotificationTemplate(models.Model):
    """Store notification templates for different types of notifications."""
    name = models.CharField(max_length=100)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    type = models.CharField(max_length=50)  # e.g., 'job_assigned', 'payment_received'
    variables = models.JSONField(default=list)  # List of required variables
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.type})"

    def render(self, context):
        """Render the template with the given context variables."""
        try:
            subject = self.subject.format(**context)
            body = self.body.format(**context)
            return subject, body
        except KeyError as e:
            raise ValueError(f"Missing required variable: {e}")

class PremiumPlan(models.Model):
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    duration_days = models.PositiveIntegerField()

    def __str__(self):
        return self.name