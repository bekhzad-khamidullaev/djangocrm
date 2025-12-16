from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Optional

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from voip.models import IncomingCall, OnlinePBXSettings
from voip.utils import find_objects_by_phone, resolve_targets, normalize_number
from voip.utils.webhook_validators import validate_onlinepbx_signature, get_client_ip
from voip.utils.webhook_helpers import rate_limit_webhook, check_webhook_idempotency

def _get_onlinepbx_backend() -> Optional[OnlinePBXSettings]:
    try:
        return OnlinePBXSettings.get_solo()
    except Exception:
        return None


# Removed: using centralized get_client_ip from webhook_validators


# Removed: replaced by centralized validate_onlinepbx_signature


def _parse_payload(request: HttpRequest) -> Dict[str, Any]:
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            return {}
    # Fallback to form data
    return {k: v for k, v in request.POST.items()}


def _extract_numbers(payload: Dict[str, Any]) -> tuple[str, str]:
    """Return caller_phone, extension/target from heterogeneous payloads."""
    caller_candidates = [
        payload.get('caller_id_number'),
        payload.get('caller_id'),
        payload.get('from'),
        payload.get('src'),
        payload.get('caller'),
        payload.get('phone'),
    ]
    target_candidates = [
        payload.get('destination_number'),
        payload.get('to'),
        payload.get('dst'),
        payload.get('extension'),
        payload.get('uid'),
        payload.get('called_did'),
    ]
    caller = next((c for c in caller_candidates if c), '')
    target = next((t for t in target_candidates if t), '')
    return str(caller), str(target)


@method_decorator(csrf_exempt, name='dispatch')
class OnlinePBXWebHook(View):
    """Webhook endpoint for OnlinePBX provider.

    Security:
    - IP allow-list via settings.VOIP entry for provider 'OnlinePBX' (IP='*' allows all)
    - Optional shared token header X-OnlinePBX-Token if settings.ONLINEPBX_WEBHOOK_TOKEN is set

    Behavior:
    - Accepts JSON or form-data payloads
    - Extracts caller phone and target extension
    - Maps to CRM objects and users, creates IncomingCall entries for targets
    """

    @rate_limit_webhook('onlinepbx', max_requests=200, window_seconds=60)
    def post(self, request: HttpRequest) -> HttpResponse:
        backend = _get_onlinepbx_backend()
        if not backend:
            return HttpResponse('OnlinePBX provider is not configured', status=503)

        # Centralized validation
        allowed_ips = [backend.allowed_ip] if backend.allowed_ip and backend.allowed_ip != '*' else None
        is_valid, error = validate_onlinepbx_signature(
            request,
            token=backend.webhook_token or None,
            allowed_ips=allowed_ips
        )
        if not is_valid:
            return HttpResponse(f'Forbidden: {error}', status=403)

        payload = _parse_payload(request)
        
        # Check idempotency
        event_id = str(payload.get('call_id') or payload.get('uuid') or '')
        event_type = str(payload.get('event_type') or payload.get('event') or '')
        if event_id and not check_webhook_idempotency('onlinepbx', event_id, event_type, payload):
            return HttpResponse('Already processed', status=200)
        caller, target_ext = _extract_numbers(payload)
        caller_norm = normalize_number(caller)

        contact = lead = deal = None
        client_name = client_type = ''
        client_id = None
        client_url = ''

        if caller_norm:
            contact, lead, deal, err = find_objects_by_phone(caller_norm)
            if not err and not (contact or lead):
                # Auto-create lead and contact
                from integrations.utils import ensure_lead_and_contact
                lead, contact = ensure_lead_and_contact(
                    source_name='onlinepbx',
                    display_name=payload.get('caller_id_name') or caller_norm,
                    phone=caller_norm,
                )
            obj = contact or lead
            if obj and hasattr(obj, 'full_name'):
                client_name = obj.full_name
                client_type = obj.__class__.__name__.lower()
                client_id = getattr(obj, 'id', None)
                # Could be enhanced with reverse URL later

        targets = resolve_targets(target_ext, contact or lead or deal)
        created = 0
        for user in targets:
            IncomingCall.objects.create(
                user=user,
                caller_id=caller_norm or caller,
                client_name=client_name,
                client_type=client_type,
                client_id=client_id,
                client_url=client_url,
                raw_payload=payload,
            )
            created += 1
        # Save CallLog for the first target (if any)
        try:
            if targets:
                from crm.models.others import CallLog
                voip_id = str(payload.get('call_id') or payload.get('uuid') or '')
                if voip_id and not CallLog.objects.filter(voip_call_id=voip_id).exists():
                    CallLog.objects.create(
                        user=targets[0],
                        contact=contact,
                        direction='inbound',
                        number=caller_norm or caller,
                        duration=int(payload.get('duration') or 0),
                        voip_call_id=voip_id,
                    )
        except Exception:
            pass

        # Mirror event into Chat hub (Lead and, if available, Request)
        try:
            from chat.models import ChatMessage
            from django.contrib.contenttypes.models import ContentType
            if lead or contact:
                obj = contact or lead
                ChatMessage.objects.create(
                    content_type=ContentType.objects.get_for_model(obj.__class__),
                    object_id=obj.id,
                    content=f"[OnlinePBX] Incoming call from {caller_norm or caller}",
                )
                # Link to most relevant Request if exists
                from crm.models import Request as Req
                req = None
                if hasattr(obj, 'request_set'):
                    req = obj.request_set.order_by('-id').first()
                if not req and deal and getattr(deal, 'request_id', None):
                    req = deal.request
                if req:
                    ChatMessage.objects.create(
                        content_type=ContentType.objects.get_for_model(Req),
                        object_id=req.id,
                        content=f"[OnlinePBX] Incoming call from {caller_norm or caller}",
                    )
        except Exception:
            pass

        return JsonResponse({
            'status': 'ok',
            'created': created,
            'targets': [u.id for u in targets],
        })
