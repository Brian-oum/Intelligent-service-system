# service_provider/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import (
    UserRegistrationForm,
    ServiceProviderForm,
    CompanyDocumentForm,
    ServiceForm
)
from .models import User, ServiceProvider, Service


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
# PROVIDER ONBOARDING
# =========================

# Step 1: Provider Account
def provider_signup_step1(request):
    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        if user_form.is_valid():
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password'])
            user.role = 'company'
            user.save()

            request.session['provider_user_id'] = user.id
            return redirect('provider_signup_step2')
    else:
        user_form = UserRegistrationForm()

    return render(request, 'Match/step1_signup.html', {'user_form': user_form})


# Step 2: Company Profile + Documents
def provider_signup_step2(request):
    user_id = request.session.get('provider_user_id')
    if not user_id:
        return redirect('provider_signup_step1')

    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        provider_form = ServiceProviderForm(request.POST, request.FILES)
        doc_forms = [
            CompanyDocumentForm(request.POST, request.FILES, prefix=str(i))
            for i in range(3)
        ]

        if provider_form.is_valid() and all(f.is_valid() for f in doc_forms):
            provider = provider_form.save(commit=False)
            provider.user = user
            provider.profile_completed = False
            provider.save()

            for f in doc_forms:
                if f.cleaned_data.get('document_file'):
                    doc = f.save(commit=False)
                    doc.service_provider = provider
                    doc.save()

            login(request, user)
            del request.session['provider_user_id']
            return redirect('add_service')

    else:
        provider_form = ServiceProviderForm()
        doc_forms = [CompanyDocumentForm(prefix=str(i)) for i in range(3)]

    return render(request, 'Match/step2_signup.html', {
        'provider_form': provider_form,
        'doc_forms': doc_forms
    })


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

    provider = get_object_or_404(ServiceProvider, user=request.user)
    services = provider.services.all()
    documents = provider.documents.all()

    return render(request, 'Match/dashboard.html', {
        'provider': provider,
        'services': services,
        'documents': documents,
    })


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
                return redirect('provider_dashboard')
            return redirect('landing_page')

        messages.error(request, "Invalid username or password.")

    return render(request, 'Match/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')
