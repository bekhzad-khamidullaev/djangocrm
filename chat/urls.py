from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import ChatMessageViewSet

app_name = 'chat'

# Create router for chat API
router = DefaultRouter()
router.register('messages', ChatMessageViewSet, basename='message')

urlpatterns = [
    path('', include(router.urls)),
]
