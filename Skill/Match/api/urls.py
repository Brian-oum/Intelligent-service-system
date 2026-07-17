from django.urls import path
from .api_views import register_api, login_api

urlpatterns = [
    path('auth/register/', register_api),
    path('auth/login/', login_api),
]