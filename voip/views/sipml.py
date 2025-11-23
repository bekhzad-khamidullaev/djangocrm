from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.conf import settings
from .models import VoIPSettings, OnlinePBXSettings
import json

class SipmlClientView(LoginRequiredMixin, TemplateView):
    template_name = "voip/sipml_client.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get VoIP settings for the user
        try:
            voip_settings = VoIPSettings.objects.filter(
                owner=self.request.user
            ).first()
            
            pbx_settings = OnlinePBXSettings.objects.filter(
                owner=self.request.user
            ).first()
            
            sip_config = {}
            if voip_settings:
                sip_config.update({
                    'websocket_uri': voip_settings.websocket_uri or '',
                    'sip_domain': voip_settings.sip_domain or '',
                    'sip_username': voip_settings.sip_username or '',
                    'display_name': voip_settings.display_name or self.request.user.get_full_name(),
                })
            
            if pbx_settings:
                sip_config.update({
                    'websocket_uri': pbx_settings.websocket_uri or sip_config.get('websocket_uri', ''),
                    'sip_domain': pbx_settings.sip_domain or sip_config.get('sip_domain', ''),
                    'sip_username': pbx_settings.sip_username or sip_config.get('sip_username', ''),
                    'display_name': pbx_settings.display_name or sip_config.get('display_name', ''),
                })
                
            context['sip_config'] = json.dumps(sip_config)
            context['user_display_name'] = self.request.user.get_full_name() or self.request.user.username
            
        except Exception as e:
            # Fallback configuration
            context['sip_config'] = json.dumps({})
            context['user_display_name'] = self.request.user.username
            
        return context
