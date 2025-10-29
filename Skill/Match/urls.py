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
]
