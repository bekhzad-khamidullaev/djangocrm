from __future__ import annotations

import hashlib
import hmac
import json
from typing import Optional
import requests

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone

from .models import ChannelAccount, ExternalMessage
from django.conf import settings
from chat.models import ChatMessage
from django.contrib.contenttypes.models import ContentType
from crm.models import Lead


def _find_telegram_account_by_secret(secret: str) -> Optional[ChannelAccount]:
    try:
        return ChannelAccount.objects.get(type='telegram', telegram_webhook_secret=secret, is_active=True)
    except ChannelAccount.DoesNotExist:
        return None


def _find_instagram_account() -> Optional[ChannelAccount]:
    return ChannelAccount.objects.filter(type='instagram', is_active=True).first()


@method_decorator(csrf_exempt, name='dispatch')
class TelegramWebhookView(View):
    def post(self, request: HttpRequest, secret: str) -> HttpResponse:
        account = _find_telegram_account_by_secret(secret)
        if not account:
            return HttpResponse('Forbidden', status=403)
        try:
            update = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            update = {}
        message = update.get('message') or update.get('edited_message')
        if not message:
            return JsonResponse({'status': 'ok'})
        chat = message.get('chat', {})
        sender = message.get('from', {})
        text = message.get('text') or ''
        ext_id = str(message.get('message_id') or update.get('update_id'))
        sender_id = str(sender.get('id') or '')
        recipient_id = str(chat.get('id') or '')

        em = ExternalMessage.objects.create(
            channel=account,
            direction='in',
            external_id=ext_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            text=text,
            raw=update,
            created_at=timezone.now(),
        )
        # Auto-create lead and contact using unified helper
        from integrations.utils import ensure_lead_and_contact
        display = sender.get('username') or f"tg:{sender_id}"
        lead, contact = ensure_lead_and_contact(
            source_name='telegram',
            display_name=str(display),
            phone='',
            email='',
            company_name=None,
        )
        # Create ChatMessage bound to Lead
        ct = ContentType.objects.get_for_model(Lead)
        ChatMessage.objects.create(
            content_type=ct,
            object_id=lead.id,
            content=text,
        )
        # Also mirror into Chat hub on Request if it exists
        from crm.models import Request
        req = Request.objects.filter(lead=lead).order_by('-id').first()
        if req:
            ChatMessage.objects.create(
                content_type=ContentType.objects.get_for_model(Request),
                object_id=req.id,
                content=f"[Telegram] {text}",
            )
        return JsonResponse({'status': 'ok'})


@method_decorator(csrf_exempt, name='dispatch')
class SendTelegramView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}
        username = (payload.get('username') or '').lstrip('@').strip()
        text = (payload.get('text') or '').strip()
        acc: Optional[ChannelAccount] = ChannelAccount.objects.filter(type='telegram', is_active=True).first()
        if not (acc and username and text):
            return JsonResponse({'status': 'error', 'detail': 'Bad request'}, status=400)
        # Real send via Telegram Bot API. User must have started chat with the bot.
        token = (acc.telegram_bot_token or '').strip()
        if not token:
            return JsonResponse({'status': 'error', 'detail': 'Telegram bot token not configured'}, status=500)
        api = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": f"@{username}", "text": text}
        try:
            resp = requests.post(api, json=payload, timeout=12)
            data = {}
            try:
                data = resp.json()
            except Exception:
                pass
            ok = resp.status_code == 200 and bool(data.get('ok'))
            ext_id = ''
            if ok:
                msg = data.get('result') or {}
                ext_id = str(msg.get('message_id') or '')
            ExternalMessage.objects.create(
                channel=acc,
                direction='out',
                external_id=ext_id,
                sender_id='bot',
                recipient_id=f"@{username}",
                text=text,
                raw=data or {"status_code": resp.status_code},
                status='SENT' if ok else 'FAILED'
            )
            if not ok:
                detail = data.get('description') or f"HTTP {resp.status_code}"
                return JsonResponse({'status': 'error', 'detail': detail}, status=502)
            return JsonResponse({'status': 'ok', 'message_id': ext_id})
        except Exception as e:
            ExternalMessage.objects.create(
                channel=acc,
                direction='out',
                external_id='',
                sender_id='bot',
                recipient_id=f"@{username}",
                text=text,
                raw={'error': str(e)},
                status='FAILED'
            )
            return JsonResponse({'status': 'error', 'detail': str(e)}, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class SendInstagramView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}
        handle = (payload.get('handle') or '').lstrip('@').strip()
        text = (payload.get('text') or '').strip()
        acc: Optional[ChannelAccount] = ChannelAccount.objects.filter(type='instagram', is_active=True).first()
        if not (acc and handle and text):
            return JsonResponse({'status': 'error', 'detail': 'Bad request'}, status=400)
        # Real send via Instagram Messaging API (Graph API)
        page_id = (acc.ig_page_id or '').strip()
        token = (acc.ig_page_access_token or '').strip()
        if not (page_id and token):
            return JsonResponse({'status': 'error', 'detail': 'Instagram page/token not configured'}, status=500)
        # Resolve Instagram handle to user ID using Graph API search endpoint (requires permissions)
        # 1) Lookup IG user ID by username via Instagram Graph API (Business Discovery)
        #    GET https://graph.facebook.com/v19.0/{page_id}?fields=business_discovery.username({handle}){id,username}
        #    Note: Requires app review permissions. We'll attempt and handle errors gracefully.
        import requests
        user_id = ''
        try:
            bd_url = f"https://graph.facebook.com/v19.0/{page_id}"
            params = {
                'fields': f"business_discovery.username({handle}){{id,username}}",
                'access_token': token,
            }
            r = requests.get(bd_url, params=params, timeout=10)
            bd = r.json()
            user_id = str(((bd.get('business_discovery') or {}).get('id')) or '')
        except Exception:
            user_id = ''
        if not user_id:
            ExternalMessage.objects.create(
                channel=acc,
                direction='out',
                external_id='',
                sender_id=page_id,
                recipient_id=f"@{handle}",
                text=text,
                raw={'note': 'IG Business Discovery failed or not permitted', 'handle': handle},
                status='FAILED'
            )
            return JsonResponse({'status': 'error', 'detail': 'Instagram handle lookup failed'}, status=502)
        # 2) Send message via Messenger API for Instagram
        #    POST https://graph.facebook.com/v19.0/{page_id}/messages
        send_url = f"https://graph.facebook.com/v19.0/{page_id}/messages"
        payload = {
            'recipient': json.dumps({'id': user_id}),
            'messaging_type': 'UPDATE',
            'message': json.dumps({'text': text}),
            'access_token': token,
        }
        resp = requests.post(send_url, data=payload, timeout=12)
        data = {}
        try:
            data = resp.json()
        except Exception:
            pass
        ok = resp.status_code == 200 and bool(data.get('id') or data.get('message_id'))
        ExternalMessage.objects.create(
            channel=acc,
            direction='out',
            external_id=str(data.get('id') or data.get('message_id') or ''),
            sender_id=page_id,
            recipient_id=user_id,
            text=text,
            raw=data or {'status_code': resp.status_code},
            status='SENT' if ok else 'FAILED'
        )
        if not ok:
            detail = data.get('error', {}).get('message') or f"HTTP {resp.status_code}"
            return JsonResponse({'status': 'error', 'detail': detail}, status=502)
        return JsonResponse({'status': 'ok', 'message_id': data.get('id') or data.get('message_id')})


@method_decorator(csrf_exempt, name='dispatch')
class InstagramWebhookView(View):
    # Verification
    def get(self, request: HttpRequest) -> HttpResponse:
        account = _find_instagram_account()
        if not account:
            return HttpResponse('No account', status=503)
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge', '')
        if mode == 'subscribe' and token == account.ig_verify_token:
            return HttpResponse(challenge)
        return HttpResponse('Forbidden', status=403)

    def post(self, request: HttpRequest) -> HttpResponse:
        account = _find_instagram_account()
        if not account:
            return HttpResponse('No account', status=503)
        # Optional signature verification
        sig = request.headers.get('X-Hub-Signature-256')
        if account.ig_app_secret and sig:
            try:
                sha_name, signature = sig.split('=')
                mac = hmac.new(account.ig_app_secret.encode('utf-8'), msg=request.body, digestmod=hashlib.sha256)
                if not hmac.compare_digest(mac.hexdigest(), signature):
                    return HttpResponse('Forbidden', status=403)
            except Exception:
                return HttpResponse('Forbidden', status=403)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}
        # Log entries as ExternalMessage (simplified; real mapping requires deeper parsing of Graph API payload)
        ext_id = str(payload.get('object') or timezone.now().timestamp())
        ExternalMessage.objects.create(
            channel=account,
            direction='in',
            external_id=ext_id,
            sender_id='',
            recipient_id=account.ig_page_id or '',
            text='',
            raw=payload,
        )
        # Auto-create lead and contact
        from integrations.utils import ensure_lead_and_contact
        lead, contact = ensure_lead_and_contact(
            source_name='instagram',
            display_name='instagram',
            phone='',
            email='',
            company_name=None,
        )
        # Mirror to Chat hub on Lead and, if available, Request
        ChatMessage.objects.create(
            content_type=ContentType.objects.get_for_model(Lead),
            object_id=lead.id,
            content='[Instagram] inbound event',
        )
        from crm.models import Request
        req = Request.objects.filter(lead=lead).order_by('-id').first()
        if req:
            ChatMessage.objects.create(
                content_type=ContentType.objects.get_for_model(Request),
                object_id=req.id,
                content='[Instagram] inbound event',
            )
        return JsonResponse({'status': 'ok'})
