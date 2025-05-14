from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    email = models.EmailField(blank=True, null=True, unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    is_verified = models.BooleanField(default=False)
    signup_method = models.CharField(max_length=10, choices=[('email', 'Email'), ('phone', 'Phone')], blank=True, null=True)  # New field

    @property
    def is_client(self):
        return hasattr(self, 'client')

    @property
    def is_worker(self):
        return hasattr(self, 'worker')

    @staticmethod
    def get_by_identifier(identifier):
        return User.objects.filter(
            models.Q(email=identifier) | models.Q(phone_number=identifier)
        ).first()

class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client')
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Client: {self.user.username}"

class Worker(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='worker')
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Worker: {self.user.username}"

class VerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)  # 6-digit code for SMS/email
    purpose = models.CharField(max_length=20, choices=[('registration', 'Registration'), ('password_reset', 'Password Reset')])
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.purpose} token for {self.user.username}"