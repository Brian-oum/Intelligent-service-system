# Register your models here.
from django.contrib import admin
from .models import User, CompanyProfile, ServiceRequest
from .utils import find_best_company

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'role', 'is_active')
    list_filter = ('role', 'is_active')

@admin.register(CompanyProfile)
class CompanyProfileAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'service_category', 'verified', 'rating', 'location')
    list_filter = ('verified', 'service_category')

@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'service_type', 'location', 'status', 'matched_company')
    list_filter = ('status', 'service_type')
    actions = ['run_matching']

    def run_matching(self, request, queryset):
        matched_count = 0
        for req in queryset.filter(status='pending'):
            best = find_best_company(req)
            if best:
                req.matched_company = best
                req.status = 'matched'
                req.save()
                matched_count += 1
        self.message_user(request, f"{matched_count} service requests matched successfully.")
    run_matching.short_description = "Run intelligent matching on selected requests"
