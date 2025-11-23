from django.apps import AppConfig


class VoipConfig(AppConfig):
    name = 'voip'
    default_auto_field = 'django.db.models.AutoField'
    verbose_name = 'VoIP Telephony'
    
    def ready(self):
        # Импортируем сигналы для автоматического создания SIP аккаунтов
        import voip.signals
