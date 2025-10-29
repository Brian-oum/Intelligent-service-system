from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from .forms import UserRegistrationForm, ServiceProviderForm, CompanyDocumentForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import User, ServiceProvider

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


# Step 1: Account Registration
def provider_signup_step1(request):
    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        if user_form.is_valid():
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password'])
            user.save()
            # Save user id in session for step 2
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
    
    user = User.objects.get(id=user_id)

    if request.method == 'POST':
        provider_form = ServiceProviderForm(request.POST, request.FILES)
        doc_forms = [CompanyDocumentForm(request.POST, request.FILES, prefix=str(x)) for x in range(0, 3)]

        forms_valid = provider_form.is_valid() and all([f.is_valid() for f in doc_forms])

        if forms_valid:
            provider = provider_form.save(commit=False)
            provider.user = user
            provider.profile_completed = True
            provider.save()

            for f in doc_forms:
                if f.cleaned_data.get('document_file'):
                    doc = f.save(commit=False)
                    doc.service_provider = provider
                    doc.save()

            login(request, user)
            # Clear session
            del request.session['provider_user_id']
            return redirect('provider_dashboard')
    else:
        provider_form = ServiceProviderForm()
        doc_forms = [CompanyDocumentForm(prefix=str(x)) for x in range(0, 3)]

    return render(request, 'Match/step2_signup.html', {
        'provider_form': provider_form,
        'doc_forms': doc_forms,
        'user': user,
    })

@login_required
def provider_dashboard(request):
    provider = ServiceProvider.objects.get(user=request.user)
    documents = provider.documents.all()
    return render(request, 'Match/dashboard.html', {'provider': provider, 'documents': documents})
# --- Login View ---
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            if user.role == 'serviceprovider':
                return redirect('provider_dashboard')  # you can later make a company dashboard
            else:
                return redirect('dashboard')  # user dashboard
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, 'Match/login.html')


# --- Logout ---
def logout_view(request):
    logout(request)
    return redirect('login')

