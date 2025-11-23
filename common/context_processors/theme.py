from django.conf import settings

def theme(request):
    """Expose admin theme flags to templates.
    theme_enabled controls loading of custom admin styles.
    theme_density_default applies density on first load; user can override via localStorage.
    """
    return {
        'theme_enabled': getattr(settings, 'ADMIN_CUSTOM_THEME', True),
        'theme_density_default': getattr(settings, 'ADMIN_DENSITY_DEFAULT', 'comfortable'),
        'comm_sms_channel_id': getattr(settings, 'COMM_SMS_CHANNEL_ID', None),
        'comm_sms_channel_name': getattr(settings, 'COMM_SMS_CHANNEL_NAME', None),
        'comm_enable_sms': getattr(settings, 'COMM_ENABLE_SMS', True),
        'comm_enable_telegram': getattr(settings, 'COMM_ENABLE_TELEGRAM', True),
        'comm_enable_instagram': getattr(settings, 'COMM_ENABLE_INSTAGRAM', True),
        'comm_enable_call': getattr(settings, 'COMM_ENABLE_CALL', True),
    }
