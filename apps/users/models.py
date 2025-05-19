from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import datetime

class User(AbstractUser):
    email = models.EmailField(blank=True, null=True, unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    is_verified = models.BooleanField(default=False)
    signup_method = models.CharField(max_length=10, choices=[('email', 'Email'), ('phone', 'Phone')], blank=True, null=True)

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
    birthdate = models.DateField(blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    has_experience = models.BooleanField(default=False)
    join_date = models.DateTimeField(default=timezone.now, null=True) 

    @property
    def years_of_experience(self):
        if self.join_date:
            delta = datetime.now(timezone.utc) - self.join_date
            years = delta.days / 365.25 
            return round(years, 2) 
        return 0.0

    def __str__(self):
        return f"Worker: {self.user.username}"

class Education(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='educations')
    institute_name = models.CharField(max_length=200)
    level_of_study = models.CharField(max_length=50)
    field_of_study = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    graduation_month = models.CharField(max_length=20)
    graduation_year = models.IntegerField()

    def __str__(self):
        return f"{self.level_of_study} in {self.field_of_study} from {self.institute_name}"

class Skill(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=100)
    level = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.name} - {self.level}"

class TargetJob(models.Model):
    worker = models.ForeignKey(Worker, on_delete=models.CASCADE, related_name='target_jobs')
    job_title = models.CharField(max_length=100)
    level = models.CharField(max_length=20)
    open_to_work = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.job_title} ({self.level}) - {'Open' if self.open_to_work else 'Closed'}"

class VerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
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