"""
WebSocket URL routing configuration for webcrm project.
"""

from django.urls import re_path
from chat.consumers import ChatConsumer, NotificationConsumer

websocket_urlpatterns = [
    # Chat WebSocket
    re_path(r'ws/chat/(?P<room_name>\w+)/$', ChatConsumer.as_asgi()),
    
    # Notifications WebSocket
    re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
]
