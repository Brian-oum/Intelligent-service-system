"""
Seeds the three standard premium-listing packages.

Place this file at:  <your_app>/management/commands/seed_subscription_plans.py
(create empty __init__.py files in management/ and management/commands/
if they don't already exist)

Run with:
    python manage.py seed_subscription_plans

Safe to re-run: it updates existing plans (matched by name) instead of
duplicating them, so tweaking the numbers below and re-running keeps
things in sync.
"""

from django.core.management.base import BaseCommand
from ...models import SubscriptionPlan


PLANS = [
    {
        "name": "Freelancer",
        "description": (
            "For solo / independent providers working on their own. "
            "Unlimited service listings and unlimited customer requests "
            "at a flat individual rate."
        ),
        "price": 1000,
        "billing_cycle": "monthly",
        "duration_days": 30,
        "max_services": None,
        "max_requests": None,
        "is_featured": False,
        "is_active": True,
    },
    {
        "name": "Starter",
        "description": (
            "For new providers dipping their toes in. Enough room to "
            "list a few services and start picking up customers."
        ),
        "price": 1500,
        "billing_cycle": "monthly",
        "duration_days": 30,
        "max_services": 3,
        "max_requests": 15,
        "is_featured": False,
        "is_active": True,
    },
    {
        "name": "Growth",
        "description": (
            "For providers ready to scale up. More listings, more "
            "customer requests, and more breathing room month to month."
        ),
        "price": 3500,
        "billing_cycle": "monthly",
        "duration_days": 30,
        "max_services": 8,
        "max_requests": 50,
        "is_featured": False,
        "is_active": True,
    },
    {
        "name": "Premium",
        "description": (
            "Unlimited listings and requests, plus a featured badge "
            "and top placement in search results."
        ),
        "price": 7000,
        "billing_cycle": "monthly",
        "duration_days": 30,
        "max_services": None,
        "max_requests": None,
        "is_featured": True,
        "is_active": True,
    },
]


class Command(BaseCommand):
    help = "Creates or updates the Starter, Growth, and Premium subscription plans."

    def handle(self, *args, **options):
        for data in PLANS:
            plan, created = SubscriptionPlan.objects.update_or_create(
                name=data["name"],
                defaults=data,
            )
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"{action}: {plan.name} (KES {plan.price}/{plan.billing_cycle})"))

        self.stdout.write(self.style.SUCCESS("Done seeding subscription plans."))