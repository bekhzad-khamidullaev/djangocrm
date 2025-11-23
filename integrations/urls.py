from django.urls import path
from .views import TelegramWebhookView, InstagramWebhookView, SendTelegramView, SendInstagramView

from .views_sms import SendSMSView

urlpatterns = [
    path('telegram/webhook/<str:secret>/', TelegramWebhookView.as_view(), name='telegram-webhook'),
    path('instagram/webhook/', InstagramWebhookView.as_view(), name='instagram-webhook'),
    path('sms/send/', SendSMSView.as_view(), name='send-sms'),
    path('telegram/send/', SendTelegramView.as_view(), name='send-telegram'),
    path('instagram/send/', SendInstagramView.as_view(), name='send-instagram'),
]
