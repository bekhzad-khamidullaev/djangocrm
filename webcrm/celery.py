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

# Add prediction schedules to beat_schedule
if hasattr(app.conf, 'beat_schedule'):
    # Analytics & Prediction tasks
    app.conf.beat_schedule.update({
        'predict-all-daily': {
            'task': 'analytics.predict_all',
            'schedule': crontab(hour=2, minute=0),  # Daily at 02:00
        },
        'predict-revenue-every-6hours': {
            'task': 'analytics.predict_revenue',
            'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
            'kwargs': {'horizon_days': 30},
        },
        'predict-next-actions-hourly': {
            'task': 'analytics.predict_next_actions',
            'schedule': crontab(minute=30),  # Every hour at :30
            'kwargs': {'limit_per_stage': 5},
        },
        'cleanup-old-forecasts-weekly': {
            'task': 'analytics.cleanup_old_forecasts',
            'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday 03:00
            'kwargs': {'days_to_keep': 90},
        },
    })
