# service_provider/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.middleware.csrf import rotate_token
from .forms import (
    UserRegistrationForm,
    ServiceProviderForm,
    CompanyDocumentForm,
    ServiceForm
)
from .models import User, ServiceProvider, Service, ServiceRequest


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
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)

            if user.role == 'company':
                provider = ServiceProvider.objects.filter(user=user).first()

                if provider and provider.profile_completed:
                    return redirect('provider_dashboard')
                else:
                    return redirect('provider_signup_step2')

            return redirect('landing_page')

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

    if request.method == 'POST':
        form = ServiceForm(request.POST)
        if form.is_valid():
            service = form.save(commit=False)
            service.provider = provider
            service.save()

            provider.profile_completed = True
            provider.save()

            return redirect('provider_dashboard')
    else:
        form = ServiceForm()

    return render(request, 'Match/add_service.html', {'form': form})


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
# PROVIDER DASHBOARD
# =========================

@login_required
def provider_dashboard(request):
    if request.user.role != 'company':
        return redirect('login')

    provider = ServiceProvider.objects.filter(user=request.user).first()

    # 🚫 HARD GATE: Ensure profile is completed
    if not provider or not provider.profile_completed:
        messages.info(request, "Complete your business profile to access the dashboard.")
        return redirect('provider_signup_step2')

    services = provider.services.all()

    # Get the latest 5 requests for this provider's services
    latest_requests = ServiceRequest.objects.filter(
        service__provider=provider
    ).order_by('-created_at')[:5]

    return render(request, 'Match/dashboard.html', {
        'provider': provider,
        'services': services,
        'latest_requests': latest_requests,
        # documents removed since we are replacing it
    })

# =========================
# SERVICE REQUEST
# =========================
def search_services(request):
    query = request.GET.get('q')

    # 🚫 If not logged in → redirect
    if not request.user.is_authenticated:
        return redirect('login')

    services = Service.objects.all()

    if query:
        services = services.filter(title__icontains=query)

    return render(request, 'Match/service_results.html', {
        'services': services,
        'query': query,
    })

@login_required
def create_request(request, service_id):
    service = Service.objects.get(id=service_id)

    if request.method == "POST":
        location = request.POST.get('location')
        description = request.POST.get('description')

        ServiceRequest.objects.create(
            user=request.user,
            service=service,
            location=location,
            description=description,
        )

        return redirect('landing_page')  # or wherever you want

    return render(request, 'Match/request.html', {
        'service': service
    })