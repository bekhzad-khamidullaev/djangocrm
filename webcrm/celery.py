from __future__ import annotations

import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webcrm.settings')

app = Celery('webcrm')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Configure beat schedule if enabled via settings
from django.conf import settings
if getattr(settings, 'ANALYTICS_FORECASTS_ENABLED', False) and getattr(settings, 'ANALYTICS_FORECASTS_CELERY_ENABLED', False):
    from celery.schedules import crontab
    app.conf.beat_schedule = getattr(app.conf, 'beat_schedule', {})
    app.conf.beat_schedule.update({
        'recompute-forecasts-nightly': {
            'task': 'analytics.tasks.recompute_forecasts_task',
            'schedule': crontab(hour=1, minute=0),
            'args': (getattr(settings, 'ANALYTICS_FORECAST_HORIZON_DAYS', 30),)
        }
    })
