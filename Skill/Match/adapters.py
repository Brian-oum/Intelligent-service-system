from allauth.account.adapter import DefaultAccountAdapter
from django.shortcuts import resolve_url

class MyAccountAdapter(DefaultAccountAdapter):

    def get_login_redirect_url(self, request):

        user = request.user

        if hasattr(user, 'role') and user.role == 'company':
            return resolve_url('provider_dashboard')

        return resolve_url('user_dashboard')