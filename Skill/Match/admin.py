# Register your models here.
from django.contrib import admin
from .models import (
    User,
    ServiceCategory,
    ServiceProvider,
    Service,
    ServiceRequest,
    Review,
    CompanyDocument
)

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
# SERVICE PROVIDERS
# =========================

@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = (
        'company_name',
        'user',
        'contact_number',
        'is_verified',
        'is_active',
        'latitude',
        'longitude'
    )

    list_filter = ('is_verified', 'is_active')
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
        ("Status", {
            "fields": (
                "profile_completed",
                "is_verified",
                "is_active"
            )
        }),
    )


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