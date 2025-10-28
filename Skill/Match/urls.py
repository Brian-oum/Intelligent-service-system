from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('get-started/', views.get_started, name='get_started'),
    path('login/', views.login_view, name='login'),
    path('register/user/', views.register_user, name='register_user'),
    path('register/company/', views.register_company, name='register_company'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('logout/', views.logout_view, name='logout'),
]
