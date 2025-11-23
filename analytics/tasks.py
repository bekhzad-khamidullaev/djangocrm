from __future__ import annotations
from celery import shared_task
from django.core.management import call_command

@shared_task
def recompute_forecasts_task(horizon: int = 30):
    call_command('recompute_forecasts', horizon=horizon)
