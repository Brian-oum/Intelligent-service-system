from .models import ServiceProvider

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
