# =========================================================================
# REPLACE the contents of your project's asgi.py with this (adjust
# 'YOUR_PROJECT_NAME' and 'service_provider' to your real names).
# =========================================================================

import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Skill.settings')

# get_asgi_application() must be called before importing anything that
# touches models, so this import order matters.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from Match.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})