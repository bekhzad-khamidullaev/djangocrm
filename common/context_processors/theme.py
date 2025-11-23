from django.conf import settings

def theme(request):
    """Expose admin theme flags to templates.
    theme_enabled controls loading of custom admin styles.
    theme_density_default applies density on first load; user can override via localStorage.
    """
    return {
        'theme_enabled': getattr(settings, 'ADMIN_CUSTOM_THEME', True),
        'theme_density_default': getattr(settings, 'ADMIN_DENSITY_DEFAULT', 'comfortable'),
    }
