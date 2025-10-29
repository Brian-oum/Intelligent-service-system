from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

USER_ROLES = (
    ('user', 'Service Seeker'),
    ('company', 'Service Provider'),
)

class User(AbstractUser):
    role = models.CharField(max_length=20, choices=USER_ROLES)
    phone = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

class ServiceProvider(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=20)
    address = models.TextField()
    website = models.URLField(blank=True, null=True)
    services_offered = models.TextField()
    logo = models.ImageField(upload_to='provider_logos/', blank=True, null=True)
    profile_completed = models.BooleanField(default=False)

    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)

    def __str__(self):
        return f"{self.company_name} ({self.user.username})"


class CompanyDocument(models.Model):
    service_provider = models.ForeignKey(ServiceProvider, on_delete=models.CASCADE, related_name='documents')
    document_name = models.CharField(max_length=255)
    document_file = models.FileField(upload_to='provider_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_name} - {self.service_provider.company_name}"
STATUS_CHOICES = (
    ('pending', 'Pending'),
    ('matched', 'Matched'),
    ('completed', 'Completed'),
)

