from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('about_page', views.about_page, name='about_page'),
    path('servivces', views.services, name='services'),
    path('get-started/', views.get_started, name='get_started'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Registration
    path('register/user/', views.register_user, name='register_user'),
    path('signup/pro/', views.provider_signup_choose_package, name='provider_signup_choose_package'),
    path('signup/step1/', views.provider_signup_step1, name='provider_signup_step1'),
    path('signup/step2/', views.provider_signup_step2, name='provider_signup_step2'),

    # ✅ FIXED DASHBOARDS
    path('user/dashboard/', views.user_dashboard, name='user_dashboard'),
    path('provider/dashboard/', views.provider_dashboard, name='provider_dashboard'),

   # Services
path('search/', views.search_services, name='search_services'),
path('request/<int:service_id>/', views.create_request, name='create_request'),
path('request/<int:service_id>/providers/', views.provider_locations_for_service, name='provider_locations_for_service'),
path('profile/', views.profile_view, name='profile'),

    path('service/add/', views.add_service, name='add_service'),
    path('service/edit/<int:service_id>/', views.edit_service, name='edit_service'),
    path('service/delete/<int:service_id>/', views.delete_service, name='delete_service'),

    # Provider Requests
    path('provider/requests/', views.provider_requests, name='provider_requests'),
    path('provider/requests/accept/<int:request_id>/', views.accept_request, name='accept_request'),
    path('provider/requests/reject/<int:request_id>/', views.reject_request, name='reject_request'),
    path('provider/requests/complete/<int:request_id>/', views.complete_request, name='complete_request'),
    path('user/requests/', views.my_requests, name='my_requests'),
    path('review/<int:request_id>/', views.submit_review, name='submit_review'),
    path('providers/<int:provider_id>/reviews/', views.provider_reviews, name='provider_reviews'),

    path('provider/services/', views.manage_services, name='manage_services'),
    path('document/view/<int:doc_id>/', views.view_document, name='view_document'),
    path('provider/<int:provider_id>/',         views.provider_report_page, name='report_page'),
    path('provider/<int:provider_id>/pdf/',     views.export_pdf,           name='export_pdf'),
    path('provider/<int:provider_id>/csv/',     views.export_csv,           name='export_csv'),
    path('api/auth/register/', views.api_register, name='api_register'),
    path("api/auth/login/", views.api_login, name="api_login"),
    # Premium listing packages
    path('packages/', views.subscription_plans, name='subscription_plans'),
    path('packages/subscribe/<int:plan_id>/', views.subscribe_to_plan, name='subscribe_to_plan'),
    path('packages/my-subscription/', views.my_subscription, name='my_subscription'),
    path('packages/renew/<int:subscription_id>/', views.renew_subscription, name='renew_subscription'),

    # Settings URLS
    path('settings/', views.settings_view, name='settings'),
    path('settings/theme/', views.update_theme_ajax, name='update_theme_ajax'),
    path('settings/avatar/upload/', views.upload_avatar_ajax, name='upload_avatar_ajax'),
    # Chat Views
    path('chat/api/conversations/', views.conversation_list, name='chat_conversation_list'),
    path('chat/api/conversations/<int:conversation_id>/messages/', views.conversation_messages, name='chat_conversation_messages'),
    path('chat/api/start/', views.start_conversation, name='chat_start_conversation'),
]