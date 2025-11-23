from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.conf import settings
from voip.models import VoipSettings, OnlinePBXSettings
import json

class SipmlClientView(LoginRequiredMixin, TemplateView):
    template_name = "voip/sipml_client.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get VoIP settings for the user
        try:
            voip_settings = VoipSettings.get_solo()
            pbx_settings = OnlinePBXSettings.get_solo()

            # Base config from PBX
            sip_config = {
                'domain': getattr(pbx_settings, 'domain', '') or '',
                'api_key': getattr(pbx_settings, 'api_key', '') or '',
                'base_url': getattr(pbx_settings, 'base_url', '') or '',
            }

            # Prefill from user profile (JsSIP fields reused for SIPml)
            prof = getattr(self.request.user, 'profile', None)
            prefill = {'realm': sip_config['domain'], 'impi': '', 'display': self.request.user.get_full_name() or self.request.user.username, 'password': ''}
            if prof:
                # Parse SIP URI like sip:1001@sip.example.com
                sip_uri = (prof.jssip_sip_uri or '').strip()
                if sip_uri.startswith('sip:') and '@' in sip_uri:
                    try:
                        userpart, realm = sip_uri[4:].split('@', 1)
                        prefill['realm'] = realm or prefill['realm']
                        prefill['impi'] = userpart or ''
                    except Exception:
                        pass
                if prof.jssip_display_name:
                    prefill['display'] = prof.jssip_display_name
                if prof.jssip_sip_password:
                    prefill['password'] = prof.jssip_sip_password

            context['sip_config'] = json.dumps(sip_config)
            context['sip_prefill'] = prefill
            context['user_display_name'] = prefill['display']

        except Exception:
            # Fallback configuration
            context['sip_config'] = json.dumps({})
            context['sip_prefill'] = {'realm': '', 'impi': '', 'display': self.request.user.username, 'password': ''}
            context['user_display_name'] = self.request.user.username
            
        return context
