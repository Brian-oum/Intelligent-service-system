from .models import ServiceProvider
import math

def find_best_company(service_request):
    """
    Matches a user's service request to the best available verified company.
    Based on service category, location, and rating.
    """
    # Step 1: Filter by service category
    companies = ServiceProvider.objects.filter(
        service_category__icontains=service_request.service_type,
        verified=True
    )

    # Step 2: Filter by location match
    companies = companies.filter(location__icontains=service_request.location)

    # Step 3: Sort by rating (highest first)
    companies = companies.order_by('-rating')

    # Step 4: Pick best match
    return companies.first() if companies.exists() else None


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two coordinates in KM
    """

    R = 6371  # Earth radius in KM

    lat1 = math.radians(float(lat1))
    lon1 = math.radians(float(lon1))
    lat2 = math.radians(float(lat2))
    lon2 = math.radians(float(lon2))

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

# utils.py
from django.core.mail import send_mail
from django.conf import settings

def send_notification_email(subject, message, recipient_email):
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,  # e.g., "noreply@yourdomain.com"
        [recipient_email],
        fail_silently=False
    )