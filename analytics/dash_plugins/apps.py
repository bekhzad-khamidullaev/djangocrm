from django.apps import AppConfig

class AnalyticsDashPluginsConfig(AppConfig):
    name = 'analytics.dash_plugins'
    verbose_name = 'Analytics Dash Plugins'

    def ready(self):
        # Safe registration when apps are ready
        try:
            from . import plugin_registry  # noqa: F401
        except Exception:
            # Avoid breaking startup if something optional is missing
            pass
