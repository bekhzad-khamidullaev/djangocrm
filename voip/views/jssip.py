from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib.auth import get_user_model
from django.contrib import messages
from voip.utils.sip_helpers import get_user_sip_config, create_sip_account_for_user


class JsSipClientView(LoginRequiredMixin, TemplateView):
    template_name = "voip/jssip_client.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Попытаться получить SIP конфигурацию из БД
        sip_config = get_user_sip_config(user)
        
        if sip_config:
            # Используем настройки из БД
            ctx["jssip"] = sip_config
            ctx["sip_account_status"] = "configured"
            ctx["internal_number"] = user.sip_account.internal_number.number
            ctx["sip_server"] = user.sip_account.internal_number.server.name
        else:
            # Попытаться автоматически создать SIP аккаунт
            try:
                sip_account = create_sip_account_for_user(user)
                sip_config = sip_account.get_jssip_config()
                ctx["jssip"] = sip_config
                ctx["sip_account_status"] = "auto_created"
                ctx["internal_number"] = sip_account.internal_number.number
                ctx["sip_server"] = sip_account.internal_number.server.name
                
                messages.success(
                    self.request, 
                    f'Автоматически создан SIP аккаунт с внутренним номером {sip_account.internal_number.number}'
                )
            except Exception as e:
                # Fallback на старую систему или настройки по умолчанию
                ctx["jssip"] = self._get_fallback_config(user)
                ctx["sip_account_status"] = "fallback"
                ctx["sip_error"] = str(e)
                
                messages.error(
                    self.request,
                    f'Не удалось настроить SIP аккаунт: {e}. Обратитесь к администратору.'
                )
        
        return ctx
    
    def _get_fallback_config(self, user):
        """Fallback конфигурация если SIP аккаунт не настроен"""
        # Попробуем использовать старую систему профилей
        profile = getattr(user, "profile", None)
        
        fallback_config = {
            "ws_uri": getattr(settings, "JSSIP_WS_URI", ""),
            "sip_uri": getattr(settings, "JSSIP_SIP_URI", ""),
            "sip_password": getattr(settings, "JSSIP_SIP_PASSWORD", ""),
            "display_name": user.get_full_name() or user.username,
        }
        
        if profile and hasattr(profile, 'jssip_ws_uri'):
            fallback_config.update({
                "ws_uri": profile.jssip_ws_uri or fallback_config["ws_uri"],
                "sip_uri": profile.jssip_sip_uri or fallback_config["sip_uri"],
                "sip_password": profile.jssip_sip_password or fallback_config["sip_password"],
                "display_name": profile.jssip_display_name or fallback_config["display_name"],
            })
        
        return fallback_config
