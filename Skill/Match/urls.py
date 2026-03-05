from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('get-started/', views.get_started, name='get_started'),
    path('login/', views.login_view, name='login'),
    path('register/user/', views.register_user, name='register_user'),
    path('signup/step1/', views.provider_signup_step1, name='provider_signup_step1'),
    path('signup/step2/', views.provider_signup_step2, name='provider_signup_step2'),
    path('dashboard/', views.provider_dashboard, name='provider_dashboard'),
    path('logout/', views.logout_view, name='logout'),
    path('search/', views.search_services, name='search_services'),
    path('request/<int:service_id>/', views.create_request, name='create_request'),
    path('profile/', views.profile_view, name='profile'),
    # Services
    path('service/add/', views.add_service, name='add_service'),
    path('service/edit/<int:service_id>/', views.edit_service, name='edit_service'),
    path('service/delete/<int:service_id>/', views.delete_service, name='delete_service'),
    path('dashboard/requests/', views.provider_requests, name='provider_requests'),
    path('dashboard/requests/accept/<int:request_id>/', views.accept_request, name='accept_request'),
    path('dashboard/requests/reject/<int:request_id>/', views.reject_request, name='reject_request'),
]
