from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.text import slugify

# =========================
# User & Roles
# =========================

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


# =========================
# Service Provider Profile
# =========================

class ServiceProvider(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255)
    contact_number = models.CharField(max_length=20)
    address = models.TextField()

    website = models.URLField(blank=True, null=True)

    profile_completed = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)


    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.company_name


# =========================
# Service Categories
# =========================

class ServiceCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


# =========================
# Services Offered
# =========================

class Service(models.Model):
    provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name='services'
    )
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE)

    title = models.CharField(max_length=150)
    description = models.TextField()

    min_price = models.DecimalField(max_digits=10, decimal_places=2)
    max_price = models.DecimalField(max_digits=10, decimal_places=2)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.provider.company_name}"


# =========================
# Company Verification Documents
# =========================

class CompanyDocument(models.Model):
    service_provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document_name = models.CharField(max_length=255)
    document_file = models.FileField(upload_to='provider_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_name} - {self.service_provider.company_name}"
