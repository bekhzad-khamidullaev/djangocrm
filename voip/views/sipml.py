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
            
            sip_config = {}
            
            # VoipSettings contains AMI configuration, not SIP client config
            # For now, provide basic fallback configuration
            if pbx_settings:
                sip_config.update({
                    'domain': pbx_settings.domain or '',
                    'api_key': pbx_settings.api_key or '',
                    'base_url': pbx_settings.base_url or '',
                    'display_name': self.request.user.get_full_name() or self.request.user.username,
                })
                
            context['sip_config'] = json.dumps(sip_config)
            context['user_display_name'] = self.request.user.get_full_name() or self.request.user.username
            
        except Exception as e:
            # Fallback configuration
            context['sip_config'] = json.dumps({})
            context['user_display_name'] = self.request.user.username
            
        return context
