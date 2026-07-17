# service_provider/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .utils import send_notification_email
from decimal import Decimal
from django.conf import settings
from django.core.mail import send_mail
from django.middleware.csrf import rotate_token
from .forms import *
from .models import *
from django.db.models import Count, Avg
from django.db.models.functions import TruncMonth
from django.utils import timezone
from datetime import timedelta
import json
from .utils import haversine_distance
from decimal import Decimal
# views.py
from django.http import FileResponse
from .models import CompanyDocument
import csv
import io
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.db.models import Count, Avg, Q, Min
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import get_user_model
import json
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.views.decorators.http import require_POST, require_GET
from django.utils.timesince import timesince
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import logging

logger = logging.getLogger(__name__)
User = get_user_model()

# =========================
# Step 2 signup: multi-service formset
# =========================
# Lets a provider list more than one service during signup (via the
# "+ Add another service" button on step2_signup.html). Built on top of
# the existing ServiceForm, so category/title/description/min_price
# validation is unchanged — this just allows repeating that form.
from django.forms import modelformset_factory

ServiceFormSet = modelformset_factory(
    Service,
    form=ServiceForm,
    extra=1,          # one empty row shown by default
    can_delete=True,  # lets JS mark extra rows for removal
    min_num=1,        # at least one service is required to sign up
    validate_min=True,
)


def _push_chat_message(convo, message, recipient_user_id):
    """
    Broadcast a freshly-created Message over the channel layer the same
    way ChatConsumer.receive() does: instantly to anyone with the thread
    open (chat_<id> group), and as a badge/inbox update to the recipient
    even if they don't (user_<id> group).

    Wrapped defensively — if the channel layer / Redis is unreachable
    (e.g. Redis isn't running locally), the message still saves to the
    DB and shows up next time the widget polls; it just won't arrive
    instantly over the socket.
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    sender_name = message.sender.get_full_name() or message.sender.username
    unread_count = convo.unread_count_for(convo.other_participant(message.sender))
    total_unread = Message.objects.filter(
        conversation__seeker_id=recipient_user_id, is_read=False
    ).exclude(sender_id=recipient_user_id).count() if convo.seeker_id == recipient_user_id else \
        Message.objects.filter(
            conversation__provider__user_id=recipient_user_id, is_read=False
        ).exclude(sender_id=recipient_user_id).count()

    try:
        async_to_sync(channel_layer.group_send)(f"chat_{convo.id}", {
            'type': 'chat.message',
            'id': message.id,
            'sender_id': message.sender_id,
            'sender_name': sender_name,
            'content': message.content,
            'created_at': message.created_at.isoformat(),
        })
        async_to_sync(channel_layer.group_send)(f"user_{recipient_user_id}", {
            'type': 'chat.notify',
            'conversation_id': convo.id,
            'sender_name': sender_name,
            'preview': message.content[:120],
            'unread_count': unread_count,
            'total_unread': total_unread,
            'created_at': message.created_at.isoformat(),
        })
    except Exception:
        logger.warning(
            "Couldn't push chat message %s over the channel layer "
            "(is Redis running?) — it was still saved to the DB.",
            message.id, exc_info=True,
        )


def view_document(request, doc_id):
    doc = get_object_or_404(CompanyDocument, id=doc_id)
    return FileResponse(open(doc.document_file.path, 'rb'), content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
# =========================
# Landing Pages
# =========================

def landing_page(request):
    return render(request, 'Match/landing.html')


def get_started(request):
    return render(request, 'Match/get_started.html')

def about_page(request):
    return render(request, 'Match/about.html')

def services(request):
    return render(request, 'Match/services.html')
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

@csrf_exempt
def api_register(request):
    if request.method != "POST":
        return JsonResponse(
            {"error": "Only POST requests are allowed"},
            status=405
        )

    try:
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        location = request.POST.get("location")

        if User.objects.filter(username=username).exists():
            return JsonResponse(
                {"success": False, "error": "Username already exists"},
                status=400
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            location=location,
            role="user"
        )

        return JsonResponse({
            "success": True,
            "message": "Registration successful",
            "user_id": user.id
        })

    except Exception as e:
        return JsonResponse(
            {"success": False, "error": str(e)},
            status=500
        )

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

@csrf_exempt
def api_login(request):
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Only POST requests allowed"},
            status=405
        )

    try:
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is None:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Invalid username or password"
                },
                status=401
            )

        login(request, user)

        provider_completed = False

        if user.role == "company":
            provider = ServiceProvider.objects.filter(
                user=user
            ).first()

            if provider:
                provider_completed = provider.profile_completed

        return JsonResponse({
            "success": True,
            "message": "Login successful",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
            "profile_completed": provider_completed
        })

    except Exception as e:
        return JsonResponse(
            {
                "success": False,
                "error": str(e)
            },
            status=500
        )

def logout_view(request):
    logout(request)
    return redirect('login')

# =========================
# Step 0: Choose a Package (Pro Signup)
# =========================

def provider_signup_choose_package(request):
    """
    Entry point for 'Sign up as Pro'. The user picks a package BEFORE
    creating their account. The chosen plan id is stashed in the
    session and applied once their ServiceProvider profile exists
    (end of Step 2).
    """
    plans = SubscriptionPlan.objects.filter(is_active=True)

    plan_id = request.GET.get('plan') or request.POST.get('plan')
    if plan_id:
        plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
        request.session['signup_plan_id'] = plan.id
        return redirect('provider_signup_step1')

    return render(request, 'Match/choose_signup_package.html', {
        'plans': plans,
    })


# =========================
# Step 1: Provider Account
# =========================
def provider_signup_step1(request):
    # A package must be chosen first.
    if 'signup_plan_id' not in request.session:
        return redirect('provider_signup_choose_package')

    selected_plan = get_object_or_404(
        SubscriptionPlan, id=request.session['signup_plan_id'], is_active=True
    )

    if request.method == 'POST':
        user_form = UserRegistrationForm(request.POST)
        if user_form.is_valid():
            user = user_form.save(commit=False)
            user.set_password(user_form.cleaned_data['password'])
            user.role = 'company'
            user.save()

            # Auto-login the new user
            # Explicitly set the backend since this user was created manually
            # (not via authenticate()), and multiple AUTHENTICATION_BACKENDS
            # are configured in settings.py.
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)

            # Redirect to Step 2
            return redirect('provider_signup_step2')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        user_form = UserRegistrationForm()

    return render(request, 'Match/step1_signup.html', {
        'user_form': user_form,
        'selected_plan': selected_plan,
    })


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

    # The plan chosen back in Step 0, if any.
    selected_plan = None
    plan_id = request.session.get('signup_plan_id')
    if plan_id:
        selected_plan = SubscriptionPlan.objects.filter(id=plan_id, is_active=True).first()

    if request.method == 'POST':
        provider_form = ServiceProviderForm(
            request.POST,
            instance=provider,
            prefix='provider'
        )

        service_formset = ServiceFormSet(
            request.POST,
            prefix='service',
            queryset=Service.objects.none(),
        )

        documents_form = CompanyDocumentsForm(
            request.POST,
            request.FILES,
            prefix='doc'
        )

        if provider_form.is_valid() and service_formset.is_valid() and documents_form.is_valid():

            # Save provider
            provider = provider_form.save(commit=False)
            provider.profile_completed = True
            provider.save()

            # Save every service the provider listed (skipping blank
            # extra rows and any marked for removal via the "Remove"
            # button). IMPORTANT: keep the category resolution logic
            # from Option 3 for each row.
            new_services = []
            for form in service_formset:
                if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                    continue
                service = form.save(commit=False)
                service.provider = provider
                service.category = form.cleaned_data['category']
                new_services.append(service)

            # Respect the chosen package's listing limit (if it has one —
            # Freelancer/Premium are unlimited, Starter/Growth are capped).
            if selected_plan and selected_plan.max_services is not None:
                new_services = new_services[:selected_plan.max_services]

            for service in new_services:
                service.save()

            # Save each verification document as its own CompanyDocument
            # row, labeled from the fixed set (Business Cert / KRA PIN / ID)
            # rather than a free-text name.
            for field_name, label in CompanyDocumentsForm.DOCUMENT_LABELS.items():
                uploaded_file = documents_form.cleaned_data.get(field_name)
                if uploaded_file:
                    CompanyDocument.objects.create(
                        service_provider=provider,
                        document_name=label,
                        document_file=uploaded_file,
                    )

            # Activate the package chosen back in Step 0
            if selected_plan:
                ProviderSubscription.objects.create(
                    provider=provider,
                    plan=selected_plan,
                    status='active',
                )
                request.session.pop('signup_plan_id', None)
                messages.success(
                    request,
                    f"Profile completed and you're now on the {selected_plan.name} package!"
                )
            else:
                messages.success(request, "Profile completed successfully!")

            return redirect('provider_dashboard')

        else:
            messages.error(request, "Please check the form for errors.")

    else:
        provider_form = ServiceProviderForm(
            instance=provider,
            prefix='provider'
        )
        service_formset = ServiceFormSet(prefix='service', queryset=Service.objects.none())
        documents_form = CompanyDocumentsForm(prefix='doc')

    context = {
        'provider_form': provider_form,
        'service_formset': service_formset,
        'documents_form': documents_form,
        'selected_plan': selected_plan,
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
    subscription = provider.active_subscription

    # ---- Package usage info (for the template's limit banner/progress bar) ----
    services_used = provider.services.filter(is_active=True).count()
    services_limit = subscription.plan.max_services if subscription else None
    limit_reached = bool(subscription and not subscription.can_add_service())
    no_package = subscription is None

    if request.method == 'POST':
        # Re-check right before saving in case usage changed since the page loaded.
        if limit_reached:
            messages.error(
                request,
                f"You've reached the service listing limit ({subscription.plan.max_services}) "
                f"for your '{subscription.plan.name}' package. Upgrade your package to list more services."
            )
            return redirect('subscription_plans')

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

            if service.min_price is None:
                messages.warning(
                    request,
                    f"{service.title} was added, but you haven't set a rate card (minimum price) for it yet. "
                    f"Add one from My Services so customers know your starting rate."
                )
            else:
                messages.success(request, f"{service.title} has been added successfully and is awaiting admin verification.")
            return redirect('manage_services')

        else:
            messages.error(request, "Please fix the errors below.")

    else:
        form = ServiceForm()

    return render(request, 'Match/add_service.html', {
        'form': form,
        'provider': provider,
        'categories': categories,
        'subscription': subscription,
        'services_used': services_used,
        'services_limit': services_limit,
        'limit_reached': limit_reached,
        'no_package': no_package,
    })


@login_required
def edit_service(request, service_id):
    if request.user.role != 'company':
        return redirect('login')

    provider = ServiceProvider.objects.filter(user=request.user).first()

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

    return render(request, 'Match/edit_service.html', {
        'form': form,
        'provider': provider
    })

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
    recent_requests = requests_qs.order_by('-created_at')[:10]

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
        messages.info(
            request,
            "Complete your business profile to access the dashboard."
        )
        return redirect('provider_signup_step2')

    # =========================================
    # BASE QUERYSET
    # =========================================
    requests_qs = ServiceRequest.objects.filter(
        provider=provider
    )

    # =========================================
    # REQUEST STATS
    # =========================================
    total_requests = requests_qs.count()

    completed_requests = requests_qs.filter(
        status='completed'
    ).count()

    pending_requests = requests_qs.filter(
        status='pending'
    ).count()

    accepted_requests = requests_qs.filter(
        status='accepted'
    ).count()

    rejected_requests = requests_qs.filter(
        status='rejected'
    ).count()

    completion_rate = (
        round((completed_requests / total_requests) * 100, 1)
        if total_requests else 0
    )

    # =========================================
    # ONLY PENDING REQUESTS FOR DASHBOARD
    # =========================================
    latest_requests = requests_qs.filter(
        status='pending'
    ).select_related(
        'service',
        'user'
    ).order_by('-created_at')[:10]

    # =========================================
    # RATINGS
    # =========================================
    avg_rating = provider.reviews.aggregate(
        avg=Avg('rating')
    )['avg']

    avg_rating = round(avg_rating, 1) if avg_rating else 0

    recent_reviews = provider.reviews.order_by(
        '-created_at'
    )[:10]

    # =========================================
    # MONTHLY TREND (LAST 6 MONTHS)
    # =========================================
    from datetime import date
    from dateutil.relativedelta import relativedelta

    today = date.today()

    months = []
    monthly_requests = []

    for i in range(5, -1, -1):

        month_start = (
            today.replace(day=1) -
            relativedelta(months=i)
        )

        month_end = month_start + relativedelta(months=1)

        month_label = month_start.strftime("%b %Y")

        months.append(month_label)

        count = requests_qs.filter(
            created_at__gte=month_start,
            created_at__lt=month_end
        ).count()

        monthly_requests.append(count)

    # =========================================
    # PACKAGE / SUBSCRIPTION SUMMARY
    # =========================================
    subscription = provider.active_subscription
    subscription_warning = bool(subscription and subscription.days_remaining <= 3)

    # =========================================
    # RATE CARD (MINIMUM PRICE) REMINDER
    # =========================================
    services_missing_rate_card = provider.services_missing_rate_card

    # =========================================
    # CONTEXT
    # =========================================
    context = {

        'provider': provider,

        # Dashboard Requests
        'latest_requests': latest_requests,

        # Rate card reminder
        'services_missing_rate_card': services_missing_rate_card,
        'missing_rate_card_count': services_missing_rate_card.count(),

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

        # Package / Subscription
        'subscription': subscription,
        'subscription_warning': subscription_warning,

        # Charts
        'months': json.dumps(months),
        'monthly_requests': json.dumps(monthly_requests),
    }

    return render(
        request,
        'Match/dashboard.html',
        context
    )
# =========================
# PREMIUM LISTING / SUBSCRIPTION PACKAGES
# =========================

@login_required
def subscription_plans(request):
    """
    Lets a company browse the available premium packages and see which
    one (if any) it's currently on.
    """
    if request.user.role != 'company':
        return redirect('login')

    provider = get_object_or_404(ServiceProvider, user=request.user)
    plans = SubscriptionPlan.objects.filter(is_active=True)
    current_subscription = provider.active_subscription

    return render(request, 'Match/subscription_plans.html', {
        'provider': provider,
        'plans': plans,
        'current_subscription': current_subscription,
    })


@login_required
def subscribe_to_plan(request, plan_id):
    """
    Subscribes the provider to a chosen plan. If they already have an
    active subscription, it's marked expired and replaced (i.e. this
    doubles as an upgrade/downgrade action).

    NOTE: this creates the subscription record directly. If you take
    payments, hook your payment gateway (e.g. M-Pesa/Stripe) in before
    this and only call it once payment is confirmed.
    """
    if request.user.role != 'company':
        return redirect('login')

    provider = get_object_or_404(ServiceProvider, user=request.user)
    plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)

    if request.method == 'POST':
        existing = provider.active_subscription
        if existing:
            existing.status = 'expired'
            existing.save(update_fields=['status'])

        ProviderSubscription.objects.create(
            provider=provider,
            plan=plan,
            status='active',
        )

        messages.success(request, f"You're now subscribed to the {plan.name} package!")
        return redirect('my_subscription')

    return render(request, 'Match/confirm_subscription.html', {
        'provider': provider,
        'plan': plan,
    })


@login_required
def my_subscription(request):
    """
    Shows the provider their current package, usage against its limits,
    and a renewal reminder as the period runs down.
    """
    if request.user.role != 'company':
        return redirect('login')

    provider = get_object_or_404(ServiceProvider, user=request.user)
    subscription = provider.active_subscription

    renewal_warning = None
    if subscription:
        if subscription.days_remaining <= 3:
            renewal_warning = (
                f"Your '{subscription.plan.name}' package expires in "
                f"{subscription.days_remaining} day(s). Renew now to avoid losing your listing limits."
            )

    history = provider.subscriptions.order_by('-created_at')[:10]

    return render(request, 'Match/my_subscription.html', {
        'provider': provider,
        'subscription': subscription,
        'renewal_warning': renewal_warning,
        'history': history,
    })


@login_required
def renew_subscription(request, subscription_id):
    """
    Renews a (usually expired, or about-to-expire) subscription into a
    fresh billing period on the same plan.
    """
    if request.user.role != 'company':
        return redirect('login')

    provider = get_object_or_404(ServiceProvider, user=request.user)
    subscription = get_object_or_404(ProviderSubscription, id=subscription_id, provider=provider)

    if request.method == 'POST':
        subscription.renew()
        messages.success(request, f"Your '{subscription.plan.name}' package has been renewed!")
        return redirect('my_subscription')

    return render(request, 'Match/confirm_renewal.html', {
        'provider': provider,
        'subscription': subscription,
    })


# =========================
# SERVICE REQUEST
# =========================

@login_required
def search_services(request):
    """
    Renders the page with:
    - a dropdown of all active+verified services (no more text-search cards)
    - the map modal, which the user opens after picking a service
    The actual "find nearby providers" step now happens via an AJAX call
    to provider_locations_for_service() below, once the user has picked
    both a service and a location.
    """
    services = Service.objects.filter(
        is_active=True,
        is_verified=True
    ).select_related('provider', 'category').order_by('title')

    context = {
        "services": services,
    }

    return render(request, "Match/service_results.html", context)


@login_required
def provider_locations_for_service(request, service_id):
    """
    AJAX endpoint: given a service and a lat/lng (query params), returns
    JSON with providers offering services in that SAME CATEGORY, within
    20km, including rating data.

    Note: Service.provider is a single FK — one Service row belongs to
    exactly one provider. So matching `services=service` directly would
    only ever return that one provider. Instead we match by category,
    the same way the original create_request view did, so every
    provider offering similar work in the area shows up as a pin.
    """
    service = get_object_or_404(Service, id=service_id, is_active=True, is_verified=True)

    user_lat = request.GET.get("lat")
    user_lng = request.GET.get("lng")

    providers = ServiceProvider.objects.filter(
        services__category=service.category,
        services__is_active=True,
        is_active=True,
        latitude__isnull=False,
        longitude__isnull=False
    ).distinct().annotate(
        avg_rating=Avg('reviews__rating'),
        review_count=Count('reviews'),
        min_price=Min(
            'services__min_price',
            filter=Q(services__category=service.category, services__is_active=True)
        ),
    )

    nearby_providers = []

    if user_lat and user_lng:
        try:
            user_lat = float(user_lat)
            user_lng = float(user_lng)
        except ValueError:
            return JsonResponse({"error": "Invalid coordinates"}, status=400)

        for provider in providers:
            distance = haversine_distance(
                user_lat,
                user_lng,
                provider.latitude,
                provider.longitude
            )
            if distance <= 20:
                nearby_providers.append((provider, round(distance, 2)))
    else:
        nearby_providers = [(p, None) for p in providers]

    # Premium (featured-plan) providers are boosted to the top of results.
    nearby_providers.sort(key=lambda pair: (not pair[0].is_premium, pair[1] if pair[1] is not None else 0))

    providers_data = [
        {
            "id": p.id,
            "name": p.company_name,
            "lat": float(p.latitude),
            "lng": float(p.longitude),
            "address": p.address,
            "rating": round(float(p.avg_rating), 1) if p.avg_rating is not None else None,
            "reviewCount": p.review_count,
            "distanceKm": dist,
            "isPremium": p.is_premium,
            "minPrice": float(p.min_price) if p.min_price is not None else None,
            # Every provider in this response was matched via
            # services__category=service.category, so this is the
            # category driving the map/list icon on the frontend.
            "category": service.category.name,
            "categorySlug": service.category.slug,
        }
        for p, dist in nearby_providers
    ]

    return JsonResponse({"providers": providers_data, "service_title": service.title})


@login_required
def provider_reviews(request, provider_id):
    """
    AJAX endpoint: returns the reviews left for a specific provider,
    most recent first, for display in the map's provider panel.
    """
    provider = get_object_or_404(ServiceProvider, id=provider_id)

    reviews_qs = Review.objects.filter(
        provider=provider
    ).select_related('user').order_by('-created_at')

    reviews_data = [
        {
            "id": r.id,
            "rating": r.rating,
            "comment": r.comment,
            "username": r.user.get_full_name() or r.user.username,
            "createdAt": r.created_at.strftime("%d %b %Y"),
        }
        for r in reviews_qs
    ]

    avg_rating = reviews_qs.aggregate(avg=Avg('rating'))['avg']

    return JsonResponse({
        "provider_id": provider.id,
        "reviews": reviews_data,
        "count": reviews_qs.count(),
        "avg_rating": round(avg_rating, 1) if avg_rating else None,
    })


@login_required
def create_request(request, service_id):

    service = get_object_or_404(Service, id=service_id)

    if request.method == "POST":

        location = request.POST.get('location')
        description = request.POST.get('description')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        provider_id = request.POST.get('provider_id')

        if not provider_id:
            messages.error(request, "Please select a provider before submitting your request.")
            return redirect('search_services')

        chosen_provider = get_object_or_404(ServiceProvider, id=provider_id)

        # Enforce the provider's plan cap on incoming customer requests, if they have a plan.
        chosen_subscription = chosen_provider.active_subscription
        if chosen_subscription and not chosen_subscription.can_receive_request():
            messages.error(
                request,
                f"{chosen_provider.company_name} has reached their request limit for this "
                f"period and can't accept new requests right now. Please try another provider."
            )
            return redirect('search_services')

        service_request = ServiceRequest.objects.create(
            user=request.user,
            service=service,
            provider=chosen_provider,
            location=location,
            description=description,
            latitude=Decimal(latitude) if latitude else None,
            longitude=Decimal(longitude) if longitude else None
        )

        if chosen_subscription:
            chosen_subscription.register_request()

        # ---- auto-open a chat thread with an automated welcome message ----
        convo, _ = Conversation.objects.get_or_create(
            seeker=request.user, provider=chosen_provider
        )
        if convo.service_request_id != service_request.id:
            convo.service_request = service_request
            convo.save(update_fields=['service_request'])

        auto_message = Message.objects.create(
            conversation=convo,
            sender=chosen_provider.user,
            content=(
                f"Hi {request.user.get_full_name() or request.user.username}, thanks for "
                f"requesting \"{service.title}\"! We've received your request and will be "
                f"in touch shortly to confirm the details."
            ),
        )
        convo.save(update_fields=[])  # bump updated_at so this thread sorts to the top

        _push_chat_message(convo, auto_message, recipient_user_id=request.user.id)

        provider_email = chosen_provider.user.email

        subject = f"New Service Request for {service.title}"

        message = f"""
Hi,

You have received a new request for "{service.title}" from {request.user.username}.

Location: {location}
Description: {description}

Please log in to your dashboard to accept or reject this request.

Thanks,
Your Service Platform
"""

        send_notification_email(subject, message, provider_email)

        messages.success(request, "Request created successfully!")

        return redirect('user_dashboard')

    return redirect('search_services')
@login_required
def profile_view(request):
    user = request.user
    if request.user.role == 'company':
        base_template = 'Match/provider_base.html'
        # ... build provider_form
    else:
        base_template = 'Match/user_base.html'

    provider = None
    user_form = None
    provider_form = None

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
        "base_template": base_template,
        "user_form": user_form,
        "provider_form": provider_form,
        "provider": provider,   # ✅ ADD THIS
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
    requests_qs = ServiceRequest.objects.filter(provider=provider).order_by('-created_at')

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
        'service', 'provider'
    ).filter(user=request.user).order_by('-created_at')

    return render(request, 'Match/my_requests.html', {
        'requests': requests_qs
    })

@login_required
def accept_request(request, request_id):
    if request.user.role != 'company':
        return redirect('login')

    service_request = get_object_or_404(ServiceRequest, id=request_id, provider__user=request.user)

    if service_request.status == 'pending':
        service_request.status = 'accepted'
        service_request.save()
        messages.success(request, f"Request for {service_request.service.title} has been accepted.")

        # ===== EMAIL TO CUSTOMER =====
        customer_email = service_request.user.email
        subject = f"Your service request for {service_request.service.title} has been accepted"
        message = f"""
Hi {service_request.user.username},

Your request for {service_request.service.title} has been accepted by {service_request.provider.company_name}.

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

    service_request = get_object_or_404(ServiceRequest, id=request_id, provider__user=request.user)

    if service_request.status != 'completed':
        service_request.status = 'completed'
        service_request.save()
        messages.success(request, f"Service '{service_request.service.title}' marked as completed.")

        # Email notification
        try:
            send_mail(
                f"Your service '{service_request.service.title}' is completed",
                f"Hi {service_request.user.username},\n\n"
                f"The service you requested from {service_request.provider.company_name} has been marked as completed.\n"
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

    service_request = get_object_or_404(ServiceRequest, id=request_id, provider__user=request.user)

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
            review.provider = service_request.provider
            review.user = request.user
            review.save()
            messages.success(request, "Thank you for your review!")
            return redirect('user_dashboard')
    else:
        form = ReviewForm()

    return render(request, 'Match/rating.html', {'form': form, 'service_request': service_request})


# ─── Helpers ──────────────────────────────────────────────────────────────────
 
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg, Count
from django.db.models.functions import TruncMonth
import json


def get_report_data(provider):
    """Aggregate all stats needed for the report."""

    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    services = provider.services.filter(is_active=True)

    from .models import ServiceRequest, Review

    requests_qs = ServiceRequest.objects.filter(provider=provider)
    reviews_qs = Review.objects.filter(provider=provider)

    # ─────────────────────────────────────────────────────
    # Main statistics
    # ─────────────────────────────────────────────────────
    total_requests = requests_qs.count()

    pending_requests = requests_qs.filter(
        status='pending'
    ).count()

    accepted_requests = requests_qs.filter(
        status='accepted'
    ).count()

    completed_requests = requests_qs.filter(
        status='completed'
    ).count()

    rejected_requests = requests_qs.filter(
        status='rejected'
    ).count()

    recent_requests = requests_qs.filter(
        created_at__gte=thirty_days_ago
    ).count()

    avg_rating = reviews_qs.aggregate(
        avg=Avg('rating')
    )['avg'] or 0

    total_reviews = reviews_qs.count()

    # ─────────────────────────────────────────────────────
    # Monthly chart data
    # ─────────────────────────────────────────────────────
    monthly_data = (
        requests_qs
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(total=Count('id'))
        .order_by('month')
    )

    months = []
    monthly_requests = []

    for item in monthly_data:
        if item['month']:
            months.append(item['month'].strftime('%b'))
            monthly_requests.append(item['total'])

    # ─────────────────────────────────────────────────────
    # Rating distribution
    # ─────────────────────────────────────────────────────
    rating_distribution = []

    for star in range(5, 0, -1):
        rating_distribution.append({
            'star': star,
            'count': reviews_qs.filter(rating=star).count()
        })

    # ─────────────────────────────────────────────────────
    # Service breakdown
    # ─────────────────────────────────────────────────────
    service_breakdown = []

    for svc in services.select_related('category'):

        svc_requests = requests_qs.filter(service=svc)

        svc_reviews = reviews_qs.filter(
            service_request__service=svc
        )

        service_breakdown.append({
            'title': svc.title,
            'category': svc.category.name,
            'total': svc_requests.count(),

            'completed': svc_requests.filter(
                status='completed'
            ).count(),

            'pending': svc_requests.filter(
                status='pending'
            ).count(),

            'rejected': svc_requests.filter(
                status='rejected'
            ).count(),

            'avg_rating': svc_reviews.aggregate(
                avg=Avg('rating')
            )['avg'] or 0,
        })

    # ─────────────────────────────────────────────────────
    # Recent requests
    # ─────────────────────────────────────────────────────
    recent_detail = (
        requests_qs
        .select_related('user', 'service')
        .order_by('-created_at')[:20]
    )

    # ─────────────────────────────────────────────────────
    # Recent reviews
    # ─────────────────────────────────────────────────────
    recent_reviews = (
        reviews_qs
        .select_related('user')
        .order_by('-created_at')[:6]
    )

    # ─────────────────────────────────────────────────────
    # Return context
    # ─────────────────────────────────────────────────────
    return {
        'provider': provider,
        'generated_at': now,
        'period': '30 days',

        'total_requests': total_requests,
        'pending_requests': pending_requests,
        'accepted_requests': accepted_requests,
        'completed_requests': completed_requests,
        'rejected_requests': rejected_requests,

        'recent_requests': recent_requests,

        'avg_rating': round(avg_rating, 1),
        'total_reviews': total_reviews,

        'total_services': services.count(),

        'service_breakdown': service_breakdown,
        'recent_detail': recent_detail,
        'recent_reviews': recent_reviews,

        'rating_distribution': rating_distribution,

        # IMPORTANT FOR CHART
        'months': json.dumps(months),
        'monthly_requests': json.dumps(monthly_requests),
    }

 
# ─── HTML Report Page ──────────────────────────────────────────────────────────
 
def provider_report_page(request, provider_id):
    """Renders the visual report page in the browser."""
    from .models import ServiceProvider
    from django.shortcuts import get_object_or_404, render
 
    provider = get_object_or_404(ServiceProvider, pk=provider_id)
    data = get_report_data(provider)
    return render(request, 'Match/report.html', data)
 
 
# ─── CSV Export ───────────────────────────────────────────────────────────────
 
def export_csv(request, provider_id):
    from .models import ServiceProvider
    from django.shortcuts import get_object_or_404
 
    provider = get_object_or_404(ServiceProvider, pk=provider_id)
    data     = get_report_data(provider)
 
    response = HttpResponse(content_type='text/csv')
    filename = f"report_{provider.company_name.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
 
    writer = csv.writer(response)
 
    # ── Summary block ──
    writer.writerow(['SERVICE PROVIDER REPORT'])
    writer.writerow(['Company', provider.company_name])
    writer.writerow(['Generated At', data['generated_at'].strftime('%d %b %Y %H:%M')])
    writer.writerow([])
 
    writer.writerow(['SUMMARY'])
    writer.writerow(['Metric', 'Value'])
    writer.writerow(['Total Services',          data['total_services']])
    writer.writerow(['Total Requests',          data['total_requests']])
    writer.writerow(['Pending',                 data['pending_requests']])
    writer.writerow(['Accepted',                data['accepted_requests']])
    writer.writerow(['Completed',               data['completed_requests']])
    writer.writerow(['Rejected',                data['rejected_requests']])
    writer.writerow(['Requests (Last 30 days)', data['recent_requests']])
    writer.writerow(['Average Rating',          data['avg_rating']])
    writer.writerow(['Total Reviews',           data['total_reviews']])
    writer.writerow([])
 
    # ── Service breakdown ──
    writer.writerow(['SERVICE BREAKDOWN'])
    writer.writerow(['Service', 'Category', 'Total Requests', 'Completed', 'Pending', 'Avg Rating'])
    for s in data['service_breakdown']:
        writer.writerow([
            s['title'], s['category'], s['total'],
            s['completed'], s['pending'],
            f"{s['avg_rating']:.1f}" if s['avg_rating'] else 'N/A'
        ])
    writer.writerow([])
 
    # ── Recent requests ──
    writer.writerow(['RECENT REQUESTS (Last 20)'])
    writer.writerow(['Date', 'Service', 'Customer', 'Location', 'Status'])
    for r in data['recent_detail']:
        writer.writerow([
            r.created_at.strftime('%d %b %Y'),
            r.service.title,
            r.user.get_full_name() or r.user.username,
            r.location,
            r.status.title(),
        ])
 
    return response
 
 
# ─── PDF Export ───────────────────────────────────────────────────────────────
 
def export_pdf(request, provider_id):
    from .models import ServiceProvider
    from django.shortcuts import get_object_or_404
 
    provider = get_object_or_404(ServiceProvider, pk=provider_id)
    data     = get_report_data(provider)
 
    buffer   = io.BytesIO()
    doc      = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm,  bottomMargin=2*cm,
    )
 
    # ── Colour palette ──
    NAVY   = colors.HexColor('#0F1B35')
    TEAL   = colors.HexColor('#0FA3B1')
    LIGHT  = colors.HexColor('#F4F7FB')
    MUTED  = colors.HexColor('#6B7A99')
    GREEN  = colors.HexColor('#22C55E')
    AMBER  = colors.HexColor('#F59E0B')
    RED    = colors.HexColor('#EF4444')
    WHITE  = colors.white
 
    styles = getSampleStyleSheet()
 
    def style(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)
 
    H1      = style('H1', fontSize=24, textColor=WHITE,    leading=30, alignment=TA_LEFT, fontName='Helvetica-Bold')
    H2      = style('H2', fontSize=13, textColor=NAVY,     leading=18, spaceBefore=14, fontName='Helvetica-Bold')
    LABEL   = style('LBL', fontSize=8, textColor=MUTED,    leading=10, fontName='Helvetica')
    NORMAL  = style('NRM', fontSize=9, textColor=NAVY,     leading=13, fontName='Helvetica')
    SMALL   = style('SML', fontSize=8, textColor=MUTED,    leading=11, fontName='Helvetica')
    CAPTION = style('CAP', fontSize=7, textColor=WHITE,    leading=10, fontName='Helvetica-Bold', alignment=TA_CENTER)
 
    story = []
 
    # ── Header banner ──
    header_data = [[
        Paragraph(f"<b>{provider.company_name}</b>", H1),
        Paragraph(
            f"<font color='#0FA3B1'>Service Provider Report</font><br/>"
            f"<font size='8' color='#A0AAC0'>Generated {data['generated_at'].strftime('%d %B %Y, %H:%M')}</font>",
            H1
        ),
    ]]
    header_table = Table(header_data, colWidths=['55%', '45%'])
    header_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,-1), NAVY),
        ('PADDING',     (0,0), (-1,-1), 18),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN',       (1,0), (1,0),   'RIGHT'),
        ('ROUNDEDCORNERS', [8]),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 20))
 
    # ── KPI cards row ──
    def kpi_cell(value, label, bg=LIGHT, txt=NAVY):
        return [
            Paragraph(f"<b>{value}</b>", ParagraphStyle('KV', fontSize=22, textColor=txt,
                       leading=26, alignment=TA_CENTER, fontName='Helvetica-Bold')),
            Paragraph(label, ParagraphStyle('KL', fontSize=8, textColor=MUTED,
                       leading=11, alignment=TA_CENTER, fontName='Helvetica')),
        ]
 
    completion_rate = (
        round(data['completed_requests'] / data['total_requests'] * 100)
        if data['total_requests'] else 0
    )
    stars = '★' * int(data['avg_rating']) + '☆' * (5 - int(data['avg_rating']))
 
    kpi_data = [
        [kpi_cell(data['total_requests'],    'Total Requests'),
         kpi_cell(data['completed_requests'], 'Completed',   bg=colors.HexColor('#ECFDF5'), txt=GREEN),
         kpi_cell(data['pending_requests'],  'Pending',      bg=colors.HexColor('#FFFBEB'), txt=AMBER),
         kpi_cell(f"{completion_rate}%",     'Completion Rate'),
         kpi_cell(f"{data['avg_rating']}",   f"Avg Rating  {stars}"),
        ]
    ]
 
    # Flatten: each kpi_cell returns a list of 2 paragraphs
    flat_kpi = [[cell for group in row for cell in group] for row in kpi_data]
    # Re-structure as 2-row table: value row + label row
    val_row   = [kpi_cell(data['total_requests'], '')[0],
                 kpi_cell(data['completed_requests'], '')[0],
                 kpi_cell(data['pending_requests'], '')[0],
                 kpi_cell(f"{completion_rate}%", '')[0],
                 kpi_cell(f"{data['avg_rating']}", '')[0]]
    label_row = [Paragraph('Total Requests', SMALL),
                 Paragraph('Completed',      SMALL),
                 Paragraph('Pending',        SMALL),
                 Paragraph('Completion Rate',SMALL),
                 Paragraph(f"Avg Rating",    SMALL)]
 
    kpi_table = Table([val_row, label_row], colWidths=['20%']*5)
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND',  (0,0), (-1,-1), LIGHT),
        ('ALIGN',       (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING',     (0,0), (-1,-1), 10),
        ('TOPPADDING',  (0,0), (-1,0),  16),
        ('BOTTOMPADDING',(0,1),(-1,1),  16),
        ('TEXTCOLOR',   (1,0), (1,1),   GREEN),
        ('TEXTCOLOR',   (2,0), (2,1),   AMBER),
        ('LINEBELOW',   (0,0), (-1,0),  0.5, colors.HexColor('#DDE3EF')),
        ('GRID',        (0,0), (-1,-1), 0.5, colors.HexColor('#DDE3EF')),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 22))
 
    # ── Request status breakdown ──
    story.append(Paragraph("Request Status Breakdown", H2))
    story.append(HRFlowable(width='100%', thickness=1, color=TEAL, spaceAfter=8))
 
    status_headers = [
        Paragraph('<b>Status</b>',  style('TH', fontSize=9, textColor=WHITE, fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Paragraph('<b>Count</b>',   style('TH', fontSize=9, textColor=WHITE, fontName='Helvetica-Bold', alignment=TA_CENTER)),
        Paragraph('<b>Share</b>',   style('TH', fontSize=9, textColor=WHITE, fontName='Helvetica-Bold', alignment=TA_CENTER)),
    ]
    statuses = [
        ('Pending',   data['pending_requests'],   AMBER),
        ('Accepted',  data['accepted_requests'],   TEAL),
        ('Completed', data['completed_requests'],  GREEN),
        ('Rejected',  data['rejected_requests'],   RED),
    ]
    status_rows = [status_headers]
    for idx, (lbl, cnt, clr) in enumerate(statuses):
        pct = round(cnt / data['total_requests'] * 100) if data['total_requests'] else 0
        status_rows.append([
            Paragraph(lbl,      NORMAL),
            Paragraph(str(cnt), style('CTR', fontSize=9, textColor=NAVY, fontName='Helvetica-Bold', alignment=TA_CENTER)),
            Paragraph(f"{pct}%",style('CTR', fontSize=9, textColor=clr,  fontName='Helvetica-Bold', alignment=TA_CENTER)),
        ])
 
    status_table = Table(status_rows, colWidths=['50%', '25%', '25%'])
    status_style = [
        ('BACKGROUND',  (0,0), (-1,0),  NAVY),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, LIGHT]),
        ('ALIGN',       (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',      (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING',     (0,0), (-1,-1), 8),
        ('ALIGN',       (0,1), (0,-1),  'LEFT'),
        ('GRID',        (0,0), (-1,-1), 0.4, colors.HexColor('#DDE3EF')),
    ]
    status_table.setStyle(TableStyle(status_style))
    story.append(status_table)
    story.append(Spacer(1, 22))
 
    # ── Service breakdown ──
    if data['service_breakdown']:
        story.append(Paragraph("Service Performance", H2))
        story.append(HRFlowable(width='100%', thickness=1, color=TEAL, spaceAfter=8))
 
        th = lambda t: Paragraph(f'<b>{t}</b>', style('TH2', fontSize=8, textColor=WHITE, fontName='Helvetica-Bold', alignment=TA_CENTER))
        svc_headers = [th('Service'), th('Category'), th('Requests'), th('Completed'), th('Pending'), th('Avg Rating')]
        svc_rows = [svc_headers]
        for s in data['service_breakdown']:
            rating_txt = f"{s['avg_rating']:.1f} ★" if s['avg_rating'] else 'N/A'
            svc_rows.append([
                Paragraph(s['title'],    NORMAL),
                Paragraph(s['category'], SMALL),
                Paragraph(str(s['total']),     style('C', fontSize=9, alignment=TA_CENTER, fontName='Helvetica')),
                Paragraph(str(s['completed']), style('C', fontSize=9, alignment=TA_CENTER, textColor=GREEN, fontName='Helvetica-Bold')),
                Paragraph(str(s['pending']),   style('C', fontSize=9, alignment=TA_CENTER, textColor=AMBER, fontName='Helvetica-Bold')),
                Paragraph(rating_txt,          style('C', fontSize=9, alignment=TA_CENTER, textColor=TEAL,  fontName='Helvetica-Bold')),
            ])
 
        svc_table = Table(svc_rows, colWidths=['28%','20%','13%','13%','13%','13%'])
        svc_table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0),  NAVY),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, LIGHT]),
            ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING',       (0,0), (-1,-1), 7),
            ('ALIGN',         (0,1), (1,-1),  'LEFT'),
            ('GRID',          (0,0), (-1,-1), 0.4, colors.HexColor('#DDE3EF')),
        ]))
        story.append(svc_table)
        story.append(Spacer(1, 22))
 
    # ── Recent requests ──
    if data['recent_detail']:
        story.append(Paragraph("Recent Requests (Last 20)", H2))
        story.append(HRFlowable(width='100%', thickness=1, color=TEAL, spaceAfter=8))
 
        STATUS_COLORS = {'pending': AMBER, 'accepted': TEAL, 'completed': GREEN, 'rejected': RED}
 
        th2 = lambda t: Paragraph(f'<b>{t}</b>', style('TH3', fontSize=8, textColor=WHITE, fontName='Helvetica-Bold'))
        req_headers = [th2('Date'), th2('Service'), th2('Customer'), th2('Location'), th2('Status')]
        req_rows = [req_headers]
        for r in data['recent_detail']:
            sc = STATUS_COLORS.get(r.status, MUTED)
            req_rows.append([
                Paragraph(r.created_at.strftime('%d %b %Y'), SMALL),
                Paragraph(r.service.title,                   NORMAL),
                Paragraph(r.user.get_full_name() or r.user.username, NORMAL),
                Paragraph(r.location[:30],                   SMALL),
                Paragraph(r.status.title(), style('ST', fontSize=8, textColor=sc, fontName='Helvetica-Bold')),
            ])
 
        req_table = Table(req_rows, colWidths=['15%','25%','20%','25%','15%'])
        req_table.setStyle(TableStyle([
            ('BACKGROUND',    (0,0), (-1,0),  NAVY),
            ('ROWBACKGROUNDS',(0,1), (-1,-1), [WHITE, LIGHT]),
            ('ALIGN',         (0,0), (-1,-1), 'LEFT'),
            ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING',       (0,0), (-1,-1), 6),
            ('GRID',          (0,0), (-1,-1), 0.4, colors.HexColor('#DDE3EF')),
        ]))
        story.append(req_table)
 
    # ── Footer ──
    story.append(Spacer(1, 30))
    story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#DDE3EF')))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"This report was auto-generated on {data['generated_at'].strftime('%d %B %Y')} · Confidential",
        style('FTR', fontSize=7, textColor=MUTED, alignment=TA_CENTER, fontName='Helvetica')
    ))
 
    doc.build(story)
    buffer.seek(0)
 
    filename = f"report_{provider.company_name.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
def settings_view(request):
    """
    Unified settings page for both Service Seekers and Providers.
    Tabs: Profile, Security, Notifications, Appearance, Privacy, Danger Zone.
    Each tab posts to the same view with a hidden `form_name` field so we
    know which sub-form to validate; the rest re-render with their current
    (unsubmitted) values.
    """
    user = request.user
    provider = None
    if user.role == 'company':
        provider, _ = ServiceProvider.objects.get_or_create(user=user)
 
    # Instantiate every form with current data by default
    if user.role == 'company':
        user_form = ServiceProviderUpdateForm(instance=provider)
    else:
        user_form = UserUpdateForm(instance=user)
 
    password_form = PasswordChangeForm(user=user)
    notif_form = NotificationSettingsForm(instance=user)
    privacy_form = PrivacySettingsForm(instance=user)
    appearance_form = AppearanceSettingsForm(instance=user)
    avatar_form = AvatarUploadForm(instance=user)
    deactivate_form = DeactivateAccountForm()
 
    active_tab = request.POST.get('form_name', request.GET.get('tab', 'profile'))
 
    if request.method == 'POST':
        form_name = request.POST.get('form_name')
 
        if form_name == 'profile':
            if user.role == 'company':
                user_form = ServiceProviderUpdateForm(request.POST, instance=provider)
            else:
                user_form = UserUpdateForm(request.POST, instance=user)
            if user_form.is_valid():
                user_form.save()
                messages.success(request, "Profile updated successfully.")
                return redirect(f"{request.path}?tab=profile")
 
        elif form_name == 'avatar':
            avatar_form = AvatarUploadForm(request.POST, request.FILES, instance=user)
            if avatar_form.is_valid():
                avatar_form.save()
                messages.success(request, "Profile photo updated.")
                return redirect(f"{request.path}?tab=profile")
 
        elif form_name == 'password':
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)  # keep user logged in
                messages.success(request, "Password changed successfully.")
                return redirect(f"{request.path}?tab=security")
 
        elif form_name == 'notifications':
            notif_form = NotificationSettingsForm(request.POST, instance=user)
            if notif_form.is_valid():
                notif_form.save()
                messages.success(request, "Notification preferences saved.")
                return redirect(f"{request.path}?tab=notifications")
 
        elif form_name == 'privacy':
            privacy_form = PrivacySettingsForm(request.POST, instance=user)
            if privacy_form.is_valid():
                privacy_form.save()
                messages.success(request, "Privacy settings saved.")
                return redirect(f"{request.path}?tab=privacy")
 
        elif form_name == 'appearance':
            appearance_form = AppearanceSettingsForm(request.POST, instance=user)
            if appearance_form.is_valid():
                appearance_form.save()
                messages.success(request, "Appearance settings saved.")
                return redirect(f"{request.path}?tab=appearance")
 
        elif form_name == 'deactivate':
            deactivate_form = DeactivateAccountForm(request.POST)
            if deactivate_form.is_valid():
                if user.check_password(deactivate_form.cleaned_data['password']):
                    user.is_active = False
                    user.save(update_fields=['is_active'])
                    logout(request)
                    messages.success(request, "Your account has been deactivated.")
                    return redirect('landing_page')
                else:
                    deactivate_form.add_error('password', 'Incorrect password.')
 
        active_tab = form_name or active_tab
 
    context = {
        'base_template': 'Match/provider_base.html' if user.role == 'company' else 'Match/user_base.html',
        'provider': provider,
        'user_form': user_form,
        'avatar_form': avatar_form,
        'password_form': password_form,
        'notif_form': notif_form,
        'privacy_form': privacy_form,
        'appearance_form': appearance_form,
        'deactivate_form': deactivate_form,
        'active_tab': active_tab,
    }
    return render(request, 'Match/settings.html', context)
 
 
@login_required
@require_POST
def update_theme_ajax(request):
    """
    Instant theme switch (no full page reload). Called from the toggle in
    the settings page (and optionally a quick-toggle in the sidebar).
    Persists the choice on the User model so it follows them across devices,
    while the client also mirrors it into localStorage for a flash-free load.
    """
    theme = request.POST.get('theme')
    if theme not in dict(User.THEME_CHOICES):
        return JsonResponse({'success': False, 'error': 'Invalid theme'}, status=400)
 
    request.user.theme_preference = theme
    request.user.save(update_fields=['theme_preference'])
    return JsonResponse({'success': True, 'theme': theme})

@login_required
@require_POST
def upload_avatar_ajax(request):
    """
    Lets a user swap their profile photo from anywhere in the app (the
    sidebar avatar, in this case) without a full page reload. Reuses
    the same AvatarUploadForm as the settings page so validation stays
    consistent between the two entry points.
    """
    form = AvatarUploadForm(request.POST, request.FILES, instance=request.user)

    if form.is_valid():
        form.save()
        return JsonResponse({
            'success': True,
            'avatar_url': request.user.avatar_url,
        })

    # Surface the first validation error (e.g. bad file type / too large)
    first_error = next(iter(form.errors.get('avatar', [])), 'Could not upload that image.')
    return JsonResponse({'success': False, 'error': first_error}, status=400)


#======================================
# CHATBOT SECTION
#======================================
def _avatar_url(user):
    return user.avatar_url
 
 
def _conversation_payload(convo, for_user):
    other = convo.other_participant(for_user)
    last = convo.last_message
    is_provider_side = for_user.id == convo.provider.user_id
    other_label = convo.seeker.get_full_name() or convo.seeker.username if is_provider_side \
        else convo.provider.company_name
 
    return {
        'id': convo.id,
        'other_user_id': other.id,
        'other_name': other_label,
        'other_avatar': _avatar_url(other),
        'last_message': last.content if last else '',
        'last_message_at': timesince(last.created_at) + ' ago' if last else '',
        'last_message_ts': last.created_at.isoformat() if last else convo.created_at.isoformat(),
        'unread_count': convo.unread_count_for(for_user),
        'service_request_id': convo.service_request_id,
        'service_title': convo.service_request.service.title if convo.service_request else None,
    }
 
 
@login_required
@require_GET
def conversation_list(request):
    user = request.user
    if user.role == 'company':
        provider = ServiceProvider.objects.filter(user=user).first()
        convos = Conversation.objects.filter(provider=provider) if provider else Conversation.objects.none()
    else:
        convos = Conversation.objects.filter(seeker=user)
 
    convos = convos.select_related('seeker', 'provider', 'provider__user', 'service_request__service')
 
    data = [_conversation_payload(c, user) for c in convos]
    total_unread = sum(c['unread_count'] for c in data)
 
    return JsonResponse({'conversations': data, 'total_unread': total_unread})
 
 
@login_required
@require_GET
def conversation_messages(request, conversation_id):
    user = request.user
    convo = get_object_or_404(Conversation, id=conversation_id)
 
    if user.id != convo.seeker_id and user.id != convo.provider.user_id:
        return JsonResponse({'error': 'Not allowed'}, status=403)
 
    convo.messages.exclude(sender=user).filter(is_read=False).update(is_read=True)
 
    messages = [
        {
            'id': m.id,
            'sender_id': m.sender_id,
            'content': m.content,
            'created_at': m.created_at.isoformat(),
            'is_own': m.sender_id == user.id,
        }
        for m in convo.messages.select_related('sender').order_by('created_at')
    ]
 
    return JsonResponse({
        'conversation': _conversation_payload(convo, user),
        'messages': messages,
    })
 
 
@login_required
@require_POST
def start_conversation(request):
    """
    Get-or-create a conversation.
 
    Seekers POST provider_id (and optionally request_id).
    Providers POST seeker_id (and optionally request_id) — e.g. replying
    to a pending request from their dashboard.
    """
    user = request.user
    request_id = request.POST.get('request_id')
    service_request = None
    if request_id:
        service_request = ServiceRequest.objects.filter(id=request_id).first()
 
    if user.role == 'company':
        provider = get_object_or_404(ServiceProvider, user=user)
        seeker_id = request.POST.get('seeker_id') or (service_request.user_id if service_request else None)
        if not seeker_id:
            return JsonResponse({'error': 'seeker_id required'}, status=400)
        convo, _ = Conversation.objects.get_or_create(seeker_id=seeker_id, provider=provider)
    else:
        provider_id = request.POST.get('provider_id') or (service_request.provider_id if service_request else None)
        if not provider_id:
            return JsonResponse({'error': 'provider_id required'}, status=400)
        provider = get_object_or_404(ServiceProvider, id=provider_id)
        convo, _ = Conversation.objects.get_or_create(seeker=user, provider=provider)
 
    if service_request and convo.service_request_id != service_request.id:
        convo.service_request = service_request
        convo.save(update_fields=['service_request'])
 
    return JsonResponse({'conversation_id': convo.id})