from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('get-started/', views.get_started, name='get_started'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Registration
    path('register/user/', views.register_user, name='register_user'),
    path('signup/step1/', views.provider_signup_step1, name='provider_signup_step1'),
    path('signup/step2/', views.provider_signup_step2, name='provider_signup_step2'),

    # ✅ FIXED DASHBOARDS
    path('user/dashboard/', views.user_dashboard, name='user_dashboard'),
    path('provider/dashboard/', views.provider_dashboard, name='provider_dashboard'),

    # Services
    path('search/', views.search_services, name='search_services'),
    path('request/<int:service_id>/', views.create_request, name='create_request'),
    path('profile/', views.profile_view, name='profile'),

    path('service/add/', views.add_service, name='add_service'),
    path('service/edit/<int:service_id>/', views.edit_service, name='edit_service'),
    path('service/delete/<int:service_id>/', views.delete_service, name='delete_service'),

    # Provider Requests
    path('provider/requests/', views.provider_requests, name='provider_requests'),
    path('provider/requests/accept/<int:request_id>/', views.accept_request, name='accept_request'),
    path('provider/requests/reject/<int:request_id>/', views.reject_request, name='reject_request'),
    path('user/requests/', views.my_requests, name='my_requests'),

    path('provider/services/', views.manage_services, name='manage_services'),
]