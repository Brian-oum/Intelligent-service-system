from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import User, CompanyProfile

# --- Landing Page ---
def landing_page(request):
    return render(request, 'Match/landing.html')


# --- Get Started Page ---
def get_started(request):
    return render(request, 'Match/get_started.html')

# --- Registration for normal user ---
def register_user(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        location = request.POST['location']

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('register_user')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            location=location,
            role='user'
        )
        messages.success(request, "Account created successfully. Please log in.")
        return redirect('login')
    return render(request, 'Match/register_user.html')


# --- Registration for company ---
def register_company(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        company_name = request.POST['company_name']
        category = request.POST['service_category']
        location = request.POST['location']

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return redirect('register_company')

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role='company',
            location=location
        )

        CompanyProfile.objects.create(
            user=user,
            company_name=company_name,
            service_category=category,
            location=location,
            verified=False
        )

        messages.success(request, "Company registered successfully. Await admin verification.")
        return redirect('login')
    return render(request, 'Match/register_company.html')


# --- Login View ---
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if user.role == 'company':
                return redirect('dashboard')  # you can later make a company dashboard
            else:
                return redirect('dashboard')  # user dashboard
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'Match/login.html')


# --- Logout ---
def logout_view(request):
    logout(request)
    return redirect('login')


# --- Dashboard (for both roles) ---
@login_required
def dashboard(request):
    if request.user.role == 'company':
        return render(request, 'Match/dashboard.html', {'role': 'Company'})
    else:
        return render(request, 'Match/dashboard.html', {'role': 'User'})
