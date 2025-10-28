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

class CompanyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_profile')
    company_name = models.CharField(max_length=200)
    service_category = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    verified = models.BooleanField(default=False)
    rating = models.FloatField(default=0.0)
    location = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.company_name
    
STATUS_CHOICES = (
    ('pending', 'Pending'),
    ('matched', 'Matched'),
    ('completed', 'Completed'),
)

class ServiceRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requests')
    service_type = models.CharField(max_length=100)
    description = models.TextField()
    location = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    date_requested = models.DateTimeField(default=timezone.now)
    matched_company = models.ForeignKey(CompanyProfile, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.service_type} - {self.user.username}"

    def save(self, *args, **kwargs):
        # ✅ Move the import *inside* the method to break circular import
        from .utils import find_best_company
        
        if not self.pk and not self.matched_company:
            best_company = find_best_company(self)
            if best_company:
                self.matched_company = best_company
                self.status = 'matched'
        super().save(*args, **kwargs)
