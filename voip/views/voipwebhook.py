import hmac
import requests
from hashlib import sha1
from base64 import b64decode
from django.conf import settings
from voip.models import ZadarmaSettings, VoipSettings
from django.http import HttpResponse
from django.http import HttpRequest
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _

from voip.utils import find_objects_by_phone, resolve_targets


@method_decorator(csrf_exempt, name='dispatch')
class VoIPWebHook(View):
    """WebHook for Zadarma VoIP provider"""

    @staticmethod
    def get(request):
        return HttpResponse(request.GET.get('zd_echo'), '')

    @staticmethod
    def post(request):
        phone: str = ''
        entry: str = ''
        data: str = ''
        e: str = ''
        init_str = full_name = deal = ''
        event = request.POST.get('event')
        if event == 'NOTIFY_RECORD':
            return HttpResponse('')
        # call status
        answered = request.POST.get('disposition') == 'answered'
        # the end of an outgoing call from the PBX
        if event == 'NOTIFY_OUT_END':
            # the phone number that was called
            init_str = _('An outgoing call to')
            phone = request.POST.get('destination')
            internal = request.POST.get('internal')
            call_start = request.POST.get('call_start')
            data = internal + phone + call_start
            
        # the end of an incoming call to the PBX extension number    
        elif event == 'NOTIFY_END':
            # the caller's phone number
            init_str = _('An incoming call from')
            phone = request.POST.get('caller_id')
            called_did = request.POST.get('called_did')
            call_start = request.POST.get('call_start')
            data = phone + called_did + call_start            
            
        if is_authenticated(request, data):
            duration_sec = int(request.POST.get('duration') or 0)
            duration = round(duration_sec/60, 1)
            duration_str = ''
            # if phone:
            contact, lead, deal, e = find_objects_by_phone(phone)
            if not e:
                obj = contact or lead
                if obj:
                    obj.was_in_touch_today()
                    full_name = obj.full_name
                if deal:
                    duration_str = _(f'(duration: {duration} minutes)')
                # Save CallLog
                try:
                    from crm.models.others import CallLog
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    # Try to pick first target user by extension/called_did
                    target_users = resolve_targets(request.POST.get('called_did') or request.POST.get('internal') or '', contact or lead or deal)
                    call_user = target_users[0] if target_users else None
                    if call_user:
                        voip_id = request.POST.get('call_id') or request.POST.get('pbx_call_id') or ''
                        existing = CallLog.objects.filter(voip_call_id=voip_id).exists() if voip_id else False
                        if not existing:
                            CallLog.objects.create(
                                user=call_user,
                                contact=contact,
                                direction='inbound' if event == 'NOTIFY_END' else 'outbound',
                                number=phone,
                                duration=duration_sec,
                                voip_call_id=voip_id,
                            )
                except Exception:
                    pass
                # Create workflow entry for the deal (outside of exception path)
                try:
                    if deal:
                        entry = f'{init_str} {full_name} {duration_str}.'
                        deal.add_to_workflow(entry)
                        deal.save()
                except Exception:
                    pass
                # Mirror into Chat hub on Lead/Request
                try:
                    from chat.models import ChatMessage
                    from django.contrib.contenttypes.models import ContentType
                    from crm.models import Request as Req
                    obj = contact or lead
                    if obj:
                        ChatMessage.objects.create(
                            content_type=ContentType.objects.get_for_model(obj.__class__),
                            object_id=obj.id,
                            content=f"[VoIP] {entry}",
                        )
                        req = None
                        if hasattr(obj, 'request_set'):
                            req = obj.request_set.order_by('-id').first()
                        elif deal and deal.request_id:
                            req = deal.request
                        if req:
                            ChatMessage.objects.create(
                                content_type=ContentType.objects.get_for_model(Req),
                                object_id=req.id,
                                content=f"[VoIP] {entry}",
                            )
                except Exception:
                    pass
                    
                if not any((contact, lead, deal)):
                    vs = VoipSettings.get_solo()
                    if vs.forward_unknown_calls and vs.forward_url:
                        headers = {}
                        sig = request.headers.get('Signature')
                        if sig:
                            headers['Signature'] = sig
                        try:
                            requests.post(vs.forward_url, data=request.POST, headers=headers, timeout=5)
                        except Exception:
                            pass

        return HttpResponse('')
    

def is_authenticated(request: HttpRequest, data: str) -> bool:
    """Authenticate Zadarma webhook using DB settings (OnlinePBXSettings zadarma_* fields)."""
    if not data:
        return False
    try:
        cfg = ZadarmaSettings.get_solo()
    except Exception:
        return False
    signature = request.headers.get('Signature')
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR', '')
    allowed_ip = (cfg.allowed_ip or '').strip()
    if allowed_ip and allowed_ip != '*' and client_ip != allowed_ip:
        # allow forwarding proxy ip if configured
        forward_ip = (cfg.webhook_forward_ip or '').strip()
        vs = VoipSettings.get_solo()
        if client_ip not in filter(None, [forward_ip, getattr(vs, 'forwarding_allowed_ip', '')]):
            return False
    secret = (cfg.secret or '').encode('utf-8')
    if not signature or not secret:
        return False
    # Zadarma signature is base64-encoded HMAC-SHA1 digest of the concatenated fields
    mac = hmac.new(secret, data.encode('utf-8'), sha1).digest()
    try:
        from base64 import b64decode
        provided = b64decode(signature)
    except Exception:
        return False
    try:
        import secrets
        return secrets.compare_digest(provided, mac)
    except Exception:
        return False
