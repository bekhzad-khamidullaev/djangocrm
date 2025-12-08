from django.conf import settings

def theme(request):
    """Expose admin theme flags to templates."""
    return {
        'theme_enabled': getattr(settings, 'ADMIN_CUSTOM_THEME', True),
        'comm_sms_channel_id': getattr(settings, 'COMM_SMS_CHANNEL_ID', None),
        'comm_sms_channel_name': getattr(settings, 'COMM_SMS_CHANNEL_NAME', None),
        'comm_enable_sms': getattr(settings, 'COMM_ENABLE_SMS', True),
        'comm_enable_telegram': getattr(settings, 'COMM_ENABLE_TELEGRAM', True),
        'comm_enable_instagram': getattr(settings, 'COMM_ENABLE_INSTAGRAM', True),
        'comm_enable_call': getattr(settings, 'COMM_ENABLE_CALL', True),
    }
