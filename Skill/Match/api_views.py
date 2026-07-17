from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q
from django.shortcuts import get_object_or_404

from .models import (
    User, ServiceProvider, ServiceCategory, Service,
    ServiceRequest, Review, CompanyDocument
)
from .serializers import (
    UserSerializer, UserRegistrationSerializer, LoginSerializer,
    ServiceProviderSerializer, ServiceCategorySerializer,
    ServiceSerializer, ServiceRequestSerializer, ServiceRequestDetailSerializer,
    ReviewSerializer, CompanyDocumentSerializer
)


class RegisterViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def user(self, request):
        """Register a new service seeker"""
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save(role='user')
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def provider_step1(self, request):
        """Register provider step 1 - create user account"""
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save(role='company')
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def provider_step2(self, request):
        """Register provider step 2 - create service provider profile"""
        user = request.user
        if user.role != 'company':
            return Response(
                {'error': 'User must be registered as a provider'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            provider = ServiceProvider.objects.get(user=user)
            serializer = ServiceProviderSerializer(provider, data=request.data, partial=True)
        except ServiceProvider.DoesNotExist:
            serializer = ServiceProviderSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save(user=user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'])
    def authenticate(self, request):
        """Login and return JWT tokens"""
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get', 'put'])
    def me(self, request):
        """Get or update current user profile"""
        if request.method == 'GET':
            serializer = UserSerializer(request.user)
            return Response(serializer.data)

        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def provider_profile(self, request):
        """Get current user's provider profile (if provider)"""
        try:
            provider = ServiceProvider.objects.get(user=request.user)
            serializer = ServiceProviderSerializer(provider)
            return Response(serializer.data)
        except ServiceProvider.DoesNotExist:
            return Response(
                {'error': 'User is not a service provider'},
                status=status.HTTP_404_NOT_FOUND
            )


class ServiceCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServiceCategory.objects.all()
    serializer_class = ServiceCategorySerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'


class ServiceViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'category__name']
    ordering_fields = ['created_at', 'title']
    ordering = ['-created_at']

    def get_queryset(self):
        return Service.objects.filter(is_active=True)

    def perform_create(self, serializer):
        try:
            provider = ServiceProvider.objects.get(user=self.request.user)
            serializer.save(provider=provider)
        except ServiceProvider.DoesNotExist:
            return Response(
                {'error': 'User must be a service provider'},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search services by category, location (lat/lon), and radius"""
        category_id = request.query_params.get('category')
        latitude = request.query_params.get('latitude')
        longitude = request.query_params.get('longitude')
        radius = request.query_params.get('radius', 50)  # Default 50 km

        queryset = self.get_queryset()

        if category_id:
            queryset = queryset.filter(category_id=category_id)

        if latitude and longitude:
            from .utils import haversine_distance
            try:
                user_lat = float(latitude)
                user_lon = float(longitude)
                radius_km = float(radius)

                filtered_services = []
                for service in queryset:
                    if service.provider.latitude and service.provider.longitude:
                        distance = haversine_distance(
                            user_lat, user_lon,
                            service.provider.latitude, service.provider.longitude
                        )
                        if distance <= radius_km:
                            filtered_services.append(service)
                queryset = queryset.filter(id__in=[s.id for s in filtered_services])
            except (ValueError, TypeError):
                pass

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def by_provider(self, request, pk=None):
        """Get all services by a specific provider"""
        queryset = Service.objects.filter(provider_id=pk, is_active=True)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ServiceRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ServiceRequestSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if user.role == 'company':
            # Provider sees requests for their services
            return ServiceRequest.objects.filter(
                service__provider__user=user
            )
        else:
            # User sees only their own requests
            return ServiceRequest.objects.filter(user=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ServiceRequestDetailSerializer
        return ServiceRequestSerializer

    @action(detail=True, methods=['patch'])
    def update_status(self, request, pk=None):
        """Update service request status"""
        service_request = self.get_object()
        new_status = request.data.get('status')

        if new_status not in dict(service_request.status_choices):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )

        service_request.status = new_status
        service_request.save()
        return Response(
            ServiceRequestDetailSerializer(service_request).data,
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """Get user's submitted requests"""
        if request.user.role != 'user':
            return Response(
                {'error': 'Only service seekers can view their requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        queryset = ServiceRequest.objects.filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def incoming_requests(self, request):
        """Get provider's incoming requests"""
        if request.user.role != 'company':
            return Response(
                {'error': 'Only providers can view incoming requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        queryset = ServiceRequest.objects.filter(
            service__provider__user=request.user
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    ordering_fields = ['created_at', 'rating']
    ordering = ['-created_at']

    def get_queryset(self):
        return Review.objects.all()

    def perform_create(self, serializer):
        service_request = serializer.validated_data['service_request']
        # Only the user who made the request can review
        if service_request.user != self.request.user:
            return Response(
                {'error': 'You can only review your own requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save(
            user=self.request.user,
            provider=service_request.service.provider
        )

    @action(detail=False, methods=['get'])
    def by_provider(self, request, pk=None):
        """Get all reviews for a specific provider"""
        provider = get_object_or_404(ServiceProvider, id=pk)
        queryset = Review.objects.filter(provider=provider)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_reviews(self, request):
        """Get reviews written by current user"""
        queryset = Review.objects.filter(user=request.user)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ServiceProviderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ServiceProvider.objects.all()
    serializer_class = ServiceProviderSerializer
    permission_classes = [AllowAny]

    @action(detail=True, methods=['get'])
    def services(self, request, pk=None):
        """Get all services offered by a provider"""
        provider = self.get_object()
        services = provider.services.filter(is_active=True)
        serializer = ServiceSerializer(services, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def reviews(self, request, pk=None):
        """Get all reviews for a provider"""
        provider = self.get_object()
        reviews = provider.reviews.all()
        serializer = ReviewSerializer(reviews, many=True)
        return Response(serializer.data)
