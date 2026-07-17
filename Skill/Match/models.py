from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.text import slugify
from django.utils import timezone
from datetime import timedelta

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
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    # ---------- SETTINGS: Appearance ----------
    THEME_CHOICES = (
        ('system', 'Match System'),
        ('light', 'Light'),
        ('dark', 'Dark'),
    )
    theme_preference = models.CharField(max_length=10, choices=THEME_CHOICES, default='system')

    # ---------- SETTINGS: Notifications ----------
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    request_update_alerts = models.BooleanField(
        default=True, help_text="Notify when a service request changes status."
    )
    marketing_emails = models.BooleanField(default=False)

    # ---------- SETTINGS: Privacy ----------
    PROFILE_VISIBILITY_CHOICES = (
        ('public', 'Public'),
        ('private', 'Private'),
    )
    profile_visibility = models.CharField(
        max_length=10, choices=PROFILE_VISIBILITY_CHOICES, default='public'
    )
    show_phone_publicly = models.BooleanField(default=True)

    # ---------- SETTINGS: Locale ----------
    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('sw', 'Kiswahili'),
    )
    preferred_language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='en')

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def avatar_url(self):
        """
        Uploaded profile photo if there is one, otherwise a generated
        initials avatar so every template can rely on this always
        returning something displayable.
        """
        if self.avatar:
            try:
                return self.avatar.url
            except Exception:
                pass
        return f"https://ui-avatars.com/api/?name={self.username}&background=1A1F2B&color=FF4D2E"


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
    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('needs_changes', 'Needs Changes'),
        ('rejected', 'Rejected'),
    ]
 
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='pending',
        help_text="Overall status of this provider's credential review.",
    )
    verification_notes = models.TextField(
        blank=True,
        help_text=(
            "Write what's missing or invalid here (e.g. 'KRA PIN certificate "
            "is blurry, please re-upload'). This text is emailed to the "
            "provider whenever you save a change to it."
        ),
    )
    verification_notes_updated_at = models.DateTimeField(null=True, blank=True)


    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.company_name

    @property
    def avatar_url(self):
        return self.user.avatar_url

    # ---------- PREMIUM / SUBSCRIPTION HELPERS ----------

    @property
    def active_subscription(self):
        """
        Returns this provider's current usable subscription (if any),
        auto-flipping it to 'expired' first if its period has lapsed.
        """
        sub = self.subscriptions.filter(status='active').order_by('-created_at').first()
        if sub:
            sub.refresh_status()
            if sub.status != 'active':
                return None
        return sub

    @property
    def is_premium(self):
        sub = self.active_subscription
        return bool(sub and sub.plan.is_featured)

    # ---------- RATE CARD HELPERS ----------

    @property
    def services_missing_rate_card(self):
        """Active services this provider hasn't set a minimum price for yet."""
        return self.services.filter(is_active=True, min_price__isnull=True)

    @property
    def has_missing_rate_cards(self):
        return self.services_missing_rate_card.exists()


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

    # ---------- RATE CARD ----------
    min_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=(
            "Your starting price for this service, in KES (e.g. 1500). "
            "Shown to customers as 'From KES X'. Leave blank if you haven't "
            "set a rate yet — you'll be reminded on your dashboard."
        ),
    )

    is_verified = models.BooleanField(default=False)  # Admin verification
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.provider.company_name}"

    @property
    def has_rate_card(self):
        return self.min_price is not None


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

# =========================
# Service Requests
# =========================

class ServiceRequest(models.Model):
    user = models.ForeignKey(
        'User', 
        on_delete=models.CASCADE, 
        related_name='requests'
    )
    service = models.ForeignKey(
        Service, 
        on_delete=models.CASCADE, 
        related_name='requests'
    )
    provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requests'
    )
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location = models.CharField(max_length=255)  # Where service is needed
    description = models.TextField(blank=True)  # Optional extra details
    status_choices = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )
    status = models.CharField(max_length=20, choices=status_choices, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.service.title} requested by {self.user.username}"

# =========================
# Reviews & Ratings
# =========================

class Review(models.Model):
    service_request = models.OneToOneField(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name='review'
    )

    provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )

    rating = models.IntegerField()  # 1 to 5
    comment = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.provider.company_name} - {self.rating}⭐"


# =========================
# Premium Listing Packages (Subscriptions)
# =========================

class SubscriptionPlan(models.Model):
    """
    A premium package a company can subscribe to. Each plan caps how many
    customers can send requests to the provider, and how many services
    the provider is allowed to list, for the duration of one billing
    period. Admins manage plans; providers subscribe/renew.
    """
    BILLING_CYCLE_CHOICES = (
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    )

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)

    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES, default='monthly')
    duration_days = models.PositiveIntegerField(
        default=30,
        help_text="Length of one subscription period in days, after which renewal is required."
    )

    max_services = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Max number of services this provider may list while subscribed. Leave blank for unlimited."
    )
    max_requests = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Max number of customer requests this provider may receive per billing period. Leave blank for unlimited."
    )

    is_featured = models.BooleanField(
        default=False,
        help_text="Featured providers are boosted/badged in search results."
    )
    is_active = models.BooleanField(default=True, help_text="Whether this plan is currently offered to providers.")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['price']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - KES {self.price}/{self.billing_cycle}"


class ProviderSubscription(models.Model):
    """
    A provider's subscription to a plan for one billing period. Tracks
    usage against the plan's limits and supports renewal into a new
    period (optionally onto a different plan, e.g. an upgrade).
    """
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )

    provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name='subscriptions'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )

    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(blank=True)

    requests_used = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    auto_renew = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = timezone.now() + timedelta(days=self.plan.duration_days)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.provider.company_name} - {self.plan.name} ({self.status})"

    # ---------- STATUS ----------

    @property
    def is_expired(self):
        return timezone.now() >= self.end_date

    @property
    def days_remaining(self):
        return max((self.end_date - timezone.now()).days, 0)

    def refresh_status(self):
        """Flip status to 'expired' if the period has lapsed. Safe to call often."""
        if self.status == 'active' and self.is_expired:
            self.status = 'expired'
            self.save(update_fields=['status'])
        return self.status

    # ---------- SERVICE LISTING LIMIT ----------

    @property
    def services_used(self):
        return self.provider.services.filter(is_active=True).count()

    @property
    def services_remaining(self):
        if self.plan.max_services is None:
            return None  # unlimited
        return max(self.plan.max_services - self.services_used, 0)

    def can_add_service(self):
        self.refresh_status()
        if self.status != 'active':
            return False
        if self.plan.max_services is None:
            return True
        return self.services_used < self.plan.max_services

    # ---------- CUSTOMER REQUEST LIMIT ----------

    @property
    def requests_remaining(self):
        if self.plan.max_requests is None:
            return None  # unlimited
        return max(self.plan.max_requests - self.requests_used, 0)

    def can_receive_request(self):
        self.refresh_status()
        if self.status != 'active':
            return False
        if self.plan.max_requests is None:
            return True
        return self.requests_used < self.plan.max_requests

    def register_request(self):
        """Call once, whenever a customer request lands on this provider."""
        self.requests_used = models.F('requests_used') + 1
        self.save(update_fields=['requests_used'])
        self.refresh_from_db()

    # ---------- RENEWAL ----------

    def renew(self, plan=None):
        """
        Closes out this period and opens a fresh one (new start/end
        dates, usage counters reset). Pass `plan` to switch package
        while renewing (e.g. upgrading Basic -> Premium).
        """
        target_plan = plan or self.plan

        if self.status == 'active':
            self.status = 'expired'
            self.save(update_fields=['status'])

        return ProviderSubscription.objects.create(
            provider=self.provider,
            plan=target_plan,
            status='active',
            auto_renew=self.auto_renew,
        )

# =========================================================================
# ADD THIS TO models.py
# (append at the end of the file — it imports nothing that isn't already
# imported at the top of models.py: models, timezone)
# =========================================================================

class Conversation(models.Model):
    """
    A single chat thread between one service seeker and one service
    provider. Optionally anchored to the ServiceRequest that started it,
    so both sides have context ("this chat is about the plumbing job").
    """
    seeker = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='seeker_conversations',
        limit_choices_to={'role': 'user'},
    )
    provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name='conversations',
    )
    service_request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    # Bumped every time a message lands — lets us order the inbox by
    # most-recently-active thread without a join/aggregate.
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('seeker', 'provider')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.seeker.username} <-> {self.provider.company_name}"

    def other_participant(self, user):
        """Given one side of the conversation, return the other side's User."""
        if user.id == self.seeker_id:
            return self.provider.user
        return self.seeker

    def unread_count_for(self, user):
        return self.messages.exclude(sender=user).filter(is_read=False).count()

    @property
    def last_message(self):
        return self.messages.order_by('-created_at').first()


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey('User', on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.username}: {self.content[:40]}"