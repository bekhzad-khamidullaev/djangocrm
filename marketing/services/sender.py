from __future__ import annotations
from typing import Optional
from django.http import JsonResponse
from django.conf import settings


def send_sms(channel_id: int, to: str, text: str):
    # Reuse integrations SendSMSView via internal import or HTTP call in future
    pass


def send_tg(username: str, text: str) -> JsonResponse:
    # Placeholder: integrate via ChannelAccount in integrations
    return JsonResponse({'status': 'not_implemented'}, status=501)


def send_ig(handle: str, text: str) -> JsonResponse:
    return JsonResponse({'status': 'not_implemented'}, status=501)
