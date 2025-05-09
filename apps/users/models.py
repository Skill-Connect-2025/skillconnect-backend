from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True, null=True, unique=True)
    email = models.EmailField(blank=True, null=True, unique=True)

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

    @property
    def is_client(self):
        return hasattr(self, 'client')

    @property
    def is_worker(self):
        return hasattr(self, 'worker')

    @classmethod
    def get_by_identifier(cls, identifier):
        return cls.objects.filter(models.Q(email=identifier) | models.Q(phone_number=identifier)).first()

class Client(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='client')

    def __str__(self):
        return f"Client: {self.user.username}"

class Worker(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='worker')
    location = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"Worker: {self.user.username}"