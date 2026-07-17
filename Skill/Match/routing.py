# service_provider/chat_routing.py
#
# Websocket URL patterns for this app. Imported by the project's asgi.py
# (see asgi_snippet.py).

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/chat/notify/$', consumers.NotifyConsumer.as_asgi()),
    re_path(r'^ws/chat/(?P<conversation_id>\d+)/$', consumers.ChatConsumer.as_asgi()),
]