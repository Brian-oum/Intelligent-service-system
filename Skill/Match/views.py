# service_provider/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.core.mail import send_mail
from django.middleware.csrf import rotate_token
from .forms import (
    UserRegistrationForm,
    ServiceProviderForm,
    CompanyDocumentForm,
    ServiceForm, 
    UserUpdateForm,
    ServiceProviderUpdateForm, 
    ReviewForm
)
from .models import User, ServiceProvider, Service, ServiceRequest, ServiceCategory
from django.db.models import Count, Avg
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
import json
from .utils import haversine_distance
from decimal import Decimal
# =========================
# Landing Pages
# =========================

def landing_page(request):
    return render(request, 'Match/landing.html')


def get_started(request):
    return render(request, 'Match/get_started.html')


# =========================
# Normal User Registration
# =========================

def register_user(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        location = request.POST['location']

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('register_user')

        User.objects.create_user(
            username=username,
            email=email,
            password=password,
            location=location,
            role='user'
        )

        messages.success(request, "Account created successfully. Please log in.")
        return redirect('login')

    return render(request, 'Match/register_user.html')

# =========================
# AUTH
# =========================

def login_view(request):
    # If user is already logged in, redirect them immediately
    if request.user.is_authenticated:
        if request.user.role == 'company':
            return redirect('provider_dashboard')
        else:
            return redirect('user_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)

            #  SERVICE PROVIDER
            if user.role == 'company':
                provider = ServiceProvider.objects.filter(user=user).first()

                if provider and provider.profile_completed:
                    return redirect('provider_dashboard')
                else:
                    return redirect('provider_signup_step2')

            #  SERVICE SEEKER (NEW FIX)
            elif user.role == 'user':
                return redirect('user_dashboard')

            #  FALLBACK (just in case)
            return redirect('landing_page')

        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'Match/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

# =========================
# Step 1: Provider Account
# =========================
def provider_signup_step1(request):
    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        if user_form.is_valid():
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password'])
            user.role = 'company'
            user.save()

            # Auto-login the new user
            login(request, user)

            # Redirect to Step 2
            return redirect('provider_signup_step2')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        user_form = UserRegistrationForm()

    return render(request, 'Match/step1_signup.html', {'user_form': user_form})


# =========================
# Step 2: Provider Profile
# =========================
@login_required
def provider_signup_step2(request):
    if request.user.role != 'company':
        return redirect('login')

    provider, created = ServiceProvider.objects.get_or_create(
        user=request.user,
        defaults={'profile_completed': False}
    )

    if provider.profile_completed:
        return redirect('provider_dashboard')

    if request.method == 'POST':
        provider_form = ServiceProviderForm(
            request.POST,
            instance=provider,
            prefix='provider'
        )

        service_form = ServiceForm(
            request.POST,
            prefix='service'
        )

        document_form = CompanyDocumentForm(
            request.POST,
            request.FILES,
            prefix='doc'
        )

        if provider_form.is_valid() and service_form.is_valid():

            # Save provider
            provider = provider_form.save(commit=False)
            provider.profile_completed = True
            provider.save()

            # Save service (IMPORTANT for Option 3 category logic)
            service = service_form.save(commit=False)
            service.provider = provider
            service.category = service_form.cleaned_data['category']
            service.save()

            # Save document ONLY if file uploaded
            if (
                document_form.is_valid()
                and document_form.cleaned_data.get('document_file')
            ):
                document = document_form.save(commit=False)
                document.service_provider = provider
                document.save()

            messages.success(request, "Profile completed successfully!")
            return redirect('provider_dashboard')

        else:
            messages.error(request, "Please check the form for errors.")

    else:
        provider_form = ServiceProviderForm(
            instance=provider,
            prefix='provider'
        )
        service_form = ServiceForm(prefix='service')
        document_form = CompanyDocumentForm(prefix='doc')

    context = {
        'provider_form': provider_form,
        'service_form': service_form,
        'document_form': document_form,
    }

    return render(request, 'Match/step2_signup.html', context)

# =========================
# SERVICES
# =========================

@login_required
def add_service(request):
    if request.user.role != 'company':
        return redirect('login')

    provider = get_object_or_404(ServiceProvider, user=request.user)
    categories = ServiceCategory.objects.all()

    if request.method == 'POST':
        form = ServiceForm(request.POST)

        if form.is_valid():
            service = form.save(commit=False)
            service.provider = provider
            service.is_active = True
            service.is_verified = False
            service.save()

            if not provider.profile_completed:
                provider.profile_completed = True
                provider.save()

            # ===== GET ADMIN EMAIL =====
            admins = User.objects.filter(is_superuser=True)
            admin_emails = [admin.email for admin in admins if admin.email]

            # ===== SEND EMAIL =====
            if admin_emails:
                try:
                    send_mail(
                        "New Service Needs Verification",
                        f"""
Hello Admin,

A new service has been added and requires verification.

Service: {service.title}
Provider: {provider.company_name}

Please log in to the admin panel to verify it.

""",
                        settings.DEFAULT_FROM_EMAIL,
                        admin_emails,
                        fail_silently=True
                    )
                except Exception as e:
                    print("Email error:", e)

            messages.success(request, f"{service.title} has been added successfully and is awaiting admin verification.")
            return redirect('manage_services')

        else:
            messages.error(request, "Please fix the errors below.")

    else:
        form = ServiceForm()

    return render(request, 'Match/add_service.html', {
        'form': form,
        'provider': provider,
        'categories': categories
    })

@login_required
def edit_service(request, service_id):
    if request.user.role != 'company':
        return redirect('login')

    service = get_object_or_404(
        Service,
        id=service_id,
        provider__user=request.user
    )

    if request.method == 'POST':
        form = ServiceForm(request.POST, instance=service)
        if form.is_valid():
            form.save()
            return redirect('provider_dashboard')
    else:
        form = ServiceForm(instance=service)

    return render(request, 'Match/edit_service.html', {'form': form})

@login_required
def manage_services(request):

    provider = ServiceProvider.objects.get(user=request.user)

    services = Service.objects.filter(provider=provider)

    return render(request, "Match/manage_services.html", {
        "provider": provider,
        "services": services
    })


@login_required
def delete_service(request, service_id):
    if request.user.role != 'company':
        return redirect('login')

    service = get_object_or_404(
        Service,
        id=service_id,
        provider__user=request.user
    )
    service.delete()
    return redirect('provider_dashboard')


# =========================
# PROVIDER  AND SEEKER DASHBOARD
# =========================
@login_required
def user_dashboard(request):

    # If a provider somehow lands here → send them to their dashboard
    if request.user.role == 'company':
        return redirect('provider_dashboard')

    # All requests made by this user
    requests_qs = ServiceRequest.objects.filter(user=request.user)

    # =============================
    # REQUEST STATS
    # =============================
    total_requests = requests_qs.count()
    pending_requests = requests_qs.filter(status='pending').count()
    accepted_requests = requests_qs.filter(status='accepted').count()
    completed_requests = requests_qs.filter(status='completed').count()
    rejected_requests = requests_qs.filter(status='rejected').count()

    # =============================
    # RECENT REQUESTS
    # =============================
    recent_requests = requests_qs.order_by('-created_at')[:5]

    # =============================
    # MONTHLY REQUEST TREND
    # =============================
    from datetime import date
    from dateutil.relativedelta import relativedelta
    import json

    today = date.today()
    months = []
    monthly_requests = []

    for i in range(5, -1, -1):
        month_start = today.replace(day=1) - relativedelta(months=i)
        month_end = month_start + relativedelta(months=1)

        months.append(month_start.strftime("%b %Y"))

        count = requests_qs.filter(
            created_at__gte=month_start,
            created_at__lt=month_end
        ).count()

        monthly_requests.append(count)

    context = {
        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'accepted_requests': accepted_requests,
        'completed_requests': completed_requests,
        'rejected_requests': rejected_requests,
        'recent_requests': recent_requests,
        'months': json.dumps(months),
        'monthly_requests': json.dumps(monthly_requests),
    }

    return render(request, 'Match/user_dashboard.html', context)

@login_required
def provider_dashboard(request):
    if request.user.role != 'company':
        return redirect('login')

    provider = ServiceProvider.objects.filter(user=request.user).first()

    if not provider or not provider.profile_completed:
        messages.info(request, "Complete your business profile to access the dashboard.")
        return redirect('provider_signup_step2')

    # Base queryset
    requests_qs = ServiceRequest.objects.filter(service__provider=provider)

    # =============================
    # REQUEST STATS
    # =============================
    total_requests = requests_qs.count()
    completed_requests = requests_qs.filter(status='completed').count()
    pending_requests = requests_qs.filter(status='pending').count()
    accepted_requests = requests_qs.filter(status='accepted').count()
    rejected_requests = requests_qs.filter(status='rejected').count()

    completion_rate = round((completed_requests / total_requests) * 100, 1) if total_requests else 0

    latest_requests = requests_qs.order_by('-created_at')[:4]  # 4 latest for dashboard

    # =============================
    # RATINGS
    # =============================
    avg_rating = provider.reviews.aggregate(avg=Avg('rating'))['avg']
    avg_rating = round(avg_rating, 1) if avg_rating is not None else None

    recent_reviews = provider.reviews.order_by('-created_at')[:5]

    # =============================
    # MONTHLY TREND (Last 6 Months)
    # =============================
    from datetime import date
    from dateutil.relativedelta import relativedelta

    today = date.today()
    months = []
    monthly_requests = []

    for i in range(5, -1, -1):  # last 6 months
        month_start = today.replace(day=1) - relativedelta(months=i)
        month_end = month_start + relativedelta(months=1)
        month_label = month_start.strftime("%b %Y")
        months.append(month_label)
        count = requests_qs.filter(
            created_at__gte=month_start,
            created_at__lt=month_end
        ).count()
        monthly_requests.append(count)

    context = {
        'provider': provider,
        'latest_requests': latest_requests,

        # Stats
        'total_requests': total_requests,
        'completed_requests': completed_requests,
        'pending_requests': pending_requests,
        'accepted_requests': accepted_requests,
        'rejected_requests': rejected_requests,
        'completion_rate': completion_rate,

        # Ratings
        'avg_rating': avg_rating,
        'recent_reviews': recent_reviews,

        # Chart
        'months': json.dumps(months),
        'monthly_requests': json.dumps(monthly_requests),
    }

    return render(request, 'Match/dashboard.html', context)
# =========================
# SERVICE REQUEST
# =========================
@login_required
def search_services(request):
    query = request.GET.get('q')
    user_lat = request.GET.get("lat")
    user_lon = request.GET.get("lon")

    # Only fetch active services
    services = Service.objects.filter(is_active=True, is_verified=True)

    # Optional: filter only providers with completed profiles
    # services = services.filter(provider__profile_completed=True)

    # Search filter
    if query:
        services = services.filter(title__icontains=query)

    results = []

    for service in services:
        provider = service.provider
        distance = None

        try:
            if user_lat and user_lon and provider.latitude and provider.longitude:
                distance = haversine_distance(
                    float(user_lat),
                    float(user_lon),
                    float(provider.latitude),
                    float(provider.longitude)
                )
        except ValueError:
            distance = None

        results.append({
            "service": service,
            "distance": round(distance, 2) if distance else None
        })

    # Sort by distance if available
    results = sorted(
        results,
        key=lambda x: x["distance"] if x["distance"] is not None else 9999
    )

    context = {
        "services": results,
        "query": query
    }

    return render(request, "Match/service_results.html", context)

from .utils import send_notification_email

@login_required
def create_request(request, service_id):
    service = get_object_or_404(Service, id=service_id)

    if request.method == "POST":
        location = request.POST.get('location')
        description = request.POST.get('description')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')

        service_request = ServiceRequest.objects.create(
            user=request.user,
            service=service,
            location=location,
            description=description,
            latitude=Decimal(latitude) if latitude else None,
            longitude=Decimal(longitude) if longitude else None
        )

        # Send email to service provider
        provider_email = service.provider.user.email
        subject = f"New Service Request for {service.title}"
        message = f"""
Hi {service.provider.user.username},

You have received a new request for your service "{service.title}" from {request.user.username}.

Location: {location}
Description: {description}

Please log in to your dashboard to accept or reject this request.

Thanks,
Your Service Platform
"""
        send_notification_email(subject, message, provider_email)

        messages.success(request, "Request created successfully!")
        return redirect('user_dashboard')

    return render(request, 'Match/request.html', {'service': service})
@login_required
def profile_view(request):
    user = request.user

    provider = None
    user_form = None
    provider_form = None

    # =========================
    # SERVICE PROVIDER
    # =========================
    if user.role == "company":

        provider, created = ServiceProvider.objects.get_or_create(user=user)

        if request.method == "POST":
            provider_form = ServiceProviderUpdateForm(request.POST, instance=provider)

            if provider_form.is_valid():
                provider_form.save()
                messages.success(request, "Company profile updated successfully!")
                return redirect("profile")

        else:
            provider_form = ServiceProviderUpdateForm(instance=provider)

    # =========================
    # SERVICE SEEKER
    # =========================
    else:

        if request.method == "POST":
            user_form = UserUpdateForm(request.POST, instance=user)

            if user_form.is_valid():
                user_form.save()
                messages.success(request, "Profile updated successfully!")
                return redirect("profile")

        else:
            user_form = UserUpdateForm(instance=user)

    context = {
        "user_form": user_form,
        "provider_form": provider_form,
    }

    return render(request, "Match/profile.html", context)

@login_required
def provider_requests(request):
    """
    Dedicated page showing all requests made to the provider's services.
    Allows filtering by status and viewing details including reviews.
    """
    if request.user.role != 'company':
        return redirect('login')

    provider = get_object_or_404(ServiceProvider, user=request.user)

    # Base queryset: all requests for this provider
    requests_qs = ServiceRequest.objects.filter(service__provider=provider).order_by('-created_at')

    # Optional filter by status
    status_filter = request.GET.get('status')
    if status_filter in ['pending', 'accepted', 'completed', 'rejected']:
        requests_qs = requests_qs.filter(status=status_filter)

    context = {
        'provider': provider,
        'service_requests': requests_qs,
        'status_filter': status_filter,
    }

    return render(request, 'Match/provider_requests.html', context)

@login_required
def my_requests(request):
    if request.user.role == 'company':
        return redirect('provider_dashboard')

    requests_qs = ServiceRequest.objects.select_related(
        'service', 'service__provider'
    ).filter(user=request.user).order_by('-created_at')

    return render(request, 'Match/my_requests.html', {
        'requests': requests_qs
    })

@login_required
def accept_request(request, request_id):
    if request.user.role != 'company':
        return redirect('login')

    service_request = get_object_or_404(ServiceRequest, id=request_id, service__provider__user=request.user)

    if service_request.status == 'pending':
        service_request.status = 'accepted'
        service_request.save()
        messages.success(request, f"Request for {service_request.service.title} has been accepted.")

        # ===== EMAIL TO CUSTOMER =====
        customer_email = service_request.user.email
        subject = f"Your service request for {service_request.service.title} has been accepted"
        message = f"""
Hi {service_request.user.username},

Your request for {service_request.service.title} has been accepted by {service_request.service.provider.company_name}.

Please log in to your dashboard for details.

Thanks,
Your Service Platform
"""
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL, 
            [customer_email],
            fail_silently=False
        )

    return redirect('provider_requests')

from django.core.mail import send_mail, BadHeaderError
import logging

@login_required
def complete_request(request, request_id):
    if request.user.role != 'company':
        return redirect('login')

    service_request = get_object_or_404(ServiceRequest, id=request_id, service__provider__user=request.user)

    if service_request.status != 'completed':
        service_request.status = 'completed'
        service_request.save()
        messages.success(request, f"Service '{service_request.service.title}' marked as completed.")

        # Email notification
        try:
            send_mail(
                f"Your service '{service_request.service.title}' is completed",
                f"Hi {service_request.user.username},\n\n"
                f"The service you requested from {service_request.service.provider.company_name} has been marked as completed.\n"
                "Please log in to provide a review.\n\nThanks,\nYour Service Platform",
                settings.DEFAULT_FROM_EMAIL,
                [service_request.user.email],
                fail_silently=False
            )
        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            messages.warning(request, "Service marked as complete, but email notification failed.")

    return redirect('provider_requests')

@login_required
def reject_request(request, request_id):
    if request.user.role != 'company':
        return redirect('login')

    service_request = get_object_or_404(ServiceRequest, id=request_id, service__provider__user=request.user)

    if service_request.status == 'pending':
        service_request.status = 'rejected'
        service_request.save()
        messages.warning(request, f"Request for {service_request.service.title} has been rejected.")

    return redirect('provider_requests')

# =========================
# SERVICE RATING
# =========================
@login_required
def submit_review(request, request_id):
    service_request = get_object_or_404(ServiceRequest, id=request_id, user=request.user)

    if service_request.status != 'completed':
        messages.error(request, "You can only review completed services.")
        return redirect('user_dashboard')

    # Prevent multiple reviews
    if hasattr(service_request, 'review'):
        messages.info(request, "You have already submitted a review for this service.")
        return redirect('user_dashboard')

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.service_request = service_request
            review.provider = service_request.service.provider
            review.user = request.user
            review.save()
            messages.success(request, "Thank you for your review!")
            return redirect('user_dashboard')
    else:
        form = ReviewForm()

    return render(request, 'Match/rating.html', {'form': form, 'service_request': service_request})