from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .api_views import (
    RegisterViewSet, LoginViewSet, UserProfileViewSet,
    ServiceCategoryViewSet, ServiceViewSet, ServiceRequestViewSet,
    ReviewViewSet, ServiceProviderViewSet
)

router = DefaultRouter()
router.register(r'auth/register', RegisterViewSet, basename='register')
router.register(r'auth/login', LoginViewSet, basename='login')
router.register(r'user', UserProfileViewSet, basename='user')
router.register(r'categories', ServiceCategoryViewSet, basename='category')
router.register(r'services', ServiceViewSet, basename='service')
router.register(r'service-requests', ServiceRequestViewSet, basename='service-request')
router.register(r'reviews', ReviewViewSet, basename='review')
router.register(r'providers', ServiceProviderViewSet, basename='provider')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
