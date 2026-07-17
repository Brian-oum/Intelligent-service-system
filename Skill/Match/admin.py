# Register your models here.
from django.contrib import admin
from .models import (
    User,
    ServiceCategory,
    ServiceProvider,
    Service,
    ServiceRequest,
    Review,
    CompanyDocument,
    SubscriptionPlan,
    ProviderSubscription,
    Conversation,
    Message,
)
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

# =========================
# USER ADMIN
# =========================

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'location', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('username', 'email')


# =========================
# SERVICE CATEGORY
# =========================

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)
    ordering = ('name',)


# =========================
# Company Documents Inline
# =========================
class CompanyDocumentInline(admin.TabularInline):
    model = CompanyDocument
    extra = 1
    fields = ('document_name', 'view_document', 'uploaded_at')
    readonly_fields = ('view_document', 'uploaded_at')

    def view_document(self, obj):
        if obj.document_file:
            url = reverse('view_document', args=[obj.id])
            return format_html('<a href="{}" target="_blank">Open Document</a>', url)
        return "No document uploaded"
    view_document.short_description = "Document"


# =========================
# Active Subscription Inline (shown on the provider page)
# =========================
class ProviderSubscriptionInline(admin.TabularInline):
    model = ProviderSubscription
    extra = 0
    fields = ('plan', 'status', 'start_date', 'end_date', 'requests_used', 'auto_renew')
    readonly_fields = ('start_date',)
    ordering = ('-created_at',)
    show_change_link = True


# =========================
# Service Provider Admin
# =========================
@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = (
        'company_name',
        'user',
        'contact_number',
        'verification_status',
        'is_verified',
        'is_active',
        'current_package',
        'latitude',
        'longitude'
    )
    list_filter = ('verification_status', 'is_verified', 'is_active')
    search_fields = ('company_name', 'user__username')
    fieldsets = (
        ("Company Info", {
            "fields": (
                "user",
                "company_name",
                "contact_number",
                "address",
                "website"
            )
        }),
        ("Location", {
            "fields": (
                "latitude",
                "longitude"
            )
        }),
        ("Credential Review", {
            "fields": (
                "verification_status",
                "verification_notes",
            ),
            "description": (
                "Use this to flag missing or invalid documents (e.g. blurry KRA "
                "PIN certificate, expired ID). Saving a change to the status or "
                "notes below automatically emails the provider with your message."
            ),
        }),
        ("Status", {
            "fields": (
                "profile_completed",
                "is_verified",
                "is_active"
            )
        }),
    )
    inlines = [CompanyDocumentInline, ProviderSubscriptionInline]
    actions = ['resend_verification_email']

    def current_package(self, obj):
        sub = obj.active_subscription
        if not sub:
            return "— none —"
        badge = " ★" if sub.plan.is_featured else ""
        return f"{sub.plan.name}{badge} ({sub.days_remaining}d left)"
    current_package.short_description = "Package"

    # ---- Email notification on credential review ----

    def save_model(self, request, obj, form, change):
        """
        Detect whether the admin changed verification_status or
        verification_notes, and if so, email the provider once the save
        completes. New providers created directly in admin (rare) don't
        trigger an email, since there's nothing to compare against yet.
        """
        should_notify = False
        if change:
            previous = ServiceProvider.objects.get(pk=obj.pk)
            should_notify = (
                previous.verification_status != obj.verification_status
                or previous.verification_notes != obj.verification_notes
            )

        super().save_model(request, obj, form, change)

        if should_notify:
            obj.verification_notes_updated_at = timezone.now()
            obj.save(update_fields=['verification_notes_updated_at'])
            self._send_verification_email(request, obj)

    def resend_verification_email(self, request, queryset):
        sent = 0
        for provider in queryset:
            if self._send_verification_email(request, provider):
                sent += 1
        self.message_user(request, f"Verification email resent to {sent} provider(s).")
    resend_verification_email.short_description = "Resend verification status email"

    def _send_verification_email(self, request, provider):
        recipient = provider.user.email if provider.user_id else None
        if not recipient:
            self.message_user(
                request,
                f"Skipped {provider.company_name}: no email address on file.",
                level="warning",
            )
            return False

        subject_map = {
            'approved': "Your Fixkona provider application has been approved",
            'needs_changes': "Action needed on your Fixkona provider application",
            'rejected': "Update on your Fixkona provider application",
            'pending': "Your Fixkona provider application is under review",
        }
        subject = subject_map.get(
            provider.verification_status,
            "Update on your Fixkona provider application",
        )

        lines = [
            f"Hi {provider.company_name},",
            "",
            f"Status: {provider.get_verification_status_display()}",
            "",
        ]
        if provider.verification_notes:
            lines += ["Notes from our review team:", provider.verification_notes, ""]
        lines += [
            "Please log in to your Fixkona dashboard to review and, if needed, "
            "re-upload your documents.",
            "",
            "Thanks,",
            "The Fixkona Team",
        ]
        message = "\n".join(lines)

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
        return True


# =========================
# SERVICES
# =========================

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'provider', 'category', 'is_active', 'is_verified', 'created_at')
    list_filter = ('is_verified', 'is_active', 'category', 'provider')
    search_fields = ('title', 'provider__company_name', 'category__name')
    actions = ['mark_as_verified']

    def mark_as_verified(self, request, queryset):
        queryset.update(is_verified=True)
        self.message_user(request, f"{queryset.count()} service(s) marked as verified.")
    mark_as_verified.short_description = "Mark selected services as verified"


# =========================
# SERVICE REQUESTS
# =========================

@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ('service', 'user', 'status', 'location', 'created_at')
    list_filter = ('status',)
    search_fields = ('user__username', 'service__title')


# =========================
# REVIEWS
# =========================

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('provider', 'user', 'rating', 'created_at')
    list_filter = ('rating',)


# =========================
# DOCUMENTS
# =========================

@admin.register(CompanyDocument)
class CompanyDocumentAdmin(admin.ModelAdmin):
    list_display = ('document_name', 'service_provider', 'uploaded_at')


# =========================
# SUBSCRIPTION PLANS (Premium Packages)
# =========================

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """
    Admins manage the packages here (Starter / Growth / Premium, or any
    custom package). Whatever is marked is_active=True automatically
    shows up on the provider-facing subscription_plans template.
    """
    list_display = (
        'name', 'price', 'billing_cycle', 'duration_days',
        'max_services', 'max_requests', 'is_featured', 'is_active', 'subscriber_count'
    )
    list_filter = ('billing_cycle', 'is_featured', 'is_active')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    ordering = ('price',)
    fieldsets = (
        ("Package Info", {
            "fields": ("name", "slug", "description", "is_active")
        }),
        ("Pricing", {
            "fields": ("price", "billing_cycle", "duration_days")
        }),
        ("Limits", {
            "fields": ("max_services", "max_requests"),
            "description": "Leave a limit blank for unlimited."
        }),
        ("Visibility", {
            "fields": ("is_featured",),
            "description": "Featured packages are boosted to the top of provider search results."
        }),
    )

    def subscriber_count(self, obj):
        return obj.subscriptions.filter(status='active').count()
    subscriber_count.short_description = "Active Subscribers"


# =========================
# PROVIDER SUBSCRIPTIONS
# =========================

@admin.register(ProviderSubscription)
class ProviderSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'provider', 'plan', 'status', 'start_date', 'end_date',
        'requests_used', 'requests_limit', 'services_used', 'services_limit', 'auto_renew'
    )
    list_filter = ('status', 'plan', 'auto_renew')
    search_fields = ('provider__company_name', 'provider__user__username')
    readonly_fields = ('start_date',)
    actions = ['renew_selected', 'mark_expired']

    def requests_limit(self, obj):
        return obj.plan.max_requests if obj.plan.max_requests is not None else "Unlimited"
    requests_limit.short_description = "Requests Limit"

    def services_limit(self, obj):
        return obj.plan.max_services if obj.plan.max_services is not None else "Unlimited"
    services_limit.short_description = "Services Limit"

    def services_used(self, obj):
        return obj.services_used
    services_used.short_description = "Services Used"

    def renew_selected(self, request, queryset):
        count = 0
        for sub in queryset:
            sub.renew()
            count += 1
        self.message_user(request, f"Renewed {count} subscription(s) into a fresh billing period.")
    renew_selected.short_description = "Renew selected subscriptions"

    def mark_expired(self, request, queryset):
        updated = queryset.update(status='expired')
        self.message_user(request, f"Marked {updated} subscription(s) as expired.")
    mark_expired.short_description = "Mark selected subscriptions as expired"


# =========================
# CHATS (Conversations & Messages)
# =========================

class MessageInline(admin.TabularInline):
    """
    Read the thread inline on the Conversation page. Messages aren't
    meant to be edited by staff, just reviewed (e.g. for disputes/abuse
    reports), so everything is read-only except the safety fields.
    """
    model = Message
    extra = 0
    fields = ('sender', 'content', 'is_read', 'created_at')
    readonly_fields = ('sender', 'content', 'created_at')
    ordering = ('created_at',)
    can_delete = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'seeker', 'provider', 'service_request',
        'message_count', 'last_activity', 'created_at',
    )
    list_filter = ('created_at',)
    search_fields = (
        'seeker__username', 'seeker__email',
        'provider__company_name', 'provider__user__username',
    )
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'updated_at'
    ordering = ('-updated_at',)
    inlines = [MessageInline]

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = "Messages"

    def last_activity(self, obj):
        last = obj.last_message
        return last.created_at if last else "—"
    last_activity.short_description = "Last message"


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Standalone flat view of every message — useful for searching across
    all conversations (e.g. moderating for a keyword) rather than
    opening each thread individually.
    """
    list_display = ('conversation', 'sender', 'short_content', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__username', 'content', 'conversation__seeker__username', 'conversation__provider__company_name')
    readonly_fields = ('conversation', 'sender', 'content', 'created_at')
    ordering = ('-created_at',)

    def short_content(self, obj):
        return obj.content[:60] + ("…" if len(obj.content) > 60 else "")
    short_content.short_description = "Message"

    def has_add_permission(self, request):
        return False