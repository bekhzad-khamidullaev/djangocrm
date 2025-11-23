from __future__ import annotations
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from analytics.models import ForecastPoint, NextActionForecast, ClientNextActionForecast
from analytics.utils.forecasting import forecast_new_leads, forecast_new_clients_with_reach, forecast_daily_revenue
from analytics.utils.funnel_forecasting import suggest_next_actions, suggest_next_actions_for_clients

SERIES_LEADS = 'leads_daily'
SERIES_CLIENTS = 'clients_daily'
SERIES_REVENUE = 'revenue_daily'

class Command(BaseCommand):
    help = 'Recompute Prophet forecasts and persist them to the database.'

    def add_arguments(self, parser):
        parser.add_argument('--horizon', type=int, default=30)
        parser.add_argument('--clear-future', action='store_true', default=True)

    def handle(self, *args, **options):
        horizon = int(options['horizon'])
        self.stdout.write(self.style.MIGRATE_HEADING('Recomputing forecasts'))
        self.recompute_leads(horizon)
        self.recompute_clients(horizon)
        self.recompute_revenue(horizon)
        self.recompute_next_actions()
        self.recompute_client_next_actions()
        self.stdout.write(self.style.SUCCESS('Done'))

    @transaction.atomic
    def recompute_leads(self, horizon: int):
        if options := forecast_new_leads(horizon):
            if options.labels:
                if ForecastPoint.objects.filter(series_key=SERIES_LEADS).exists():
                    ForecastPoint.objects.filter(series_key=SERIES_LEADS, date__gte=date.today()).delete()
                for d, y, yl, yu in zip(options.labels, options.yhat, options.yhat_lower or [], options.yhat_upper or []):
                    ForecastPoint.objects.update_or_create(
                        series_key=SERIES_LEADS,
                        date=d,
                        defaults={'yhat': y, 'yhat_lower': yl if yl is not None else y, 'yhat_upper': yu if yu is not None else y}
                    )

    @transaction.atomic
    def recompute_clients(self, horizon: int):
        if options := forecast_new_clients_with_reach(horizon):
            if options.labels:
                if ForecastPoint.objects.filter(series_key=SERIES_CLIENTS).exists():
                    ForecastPoint.objects.filter(series_key=SERIES_CLIENTS, date__gte=date.today()).delete()
                for d, y, yl, yu in zip(options.labels, options.yhat, options.yhat_lower or [], options.yhat_upper or []):
                    ForecastPoint.objects.update_or_create(
                        series_key=SERIES_CLIENTS,
                        date=d,
                        defaults={'yhat': y, 'yhat_lower': yl if yl is not None else y, 'yhat_upper': yu if yu is not None else y}
                    )

    @transaction.atomic
    def recompute_revenue(self, horizon: int):
        if options := forecast_daily_revenue(horizon):
            if options.labels:
                if ForecastPoint.objects.filter(series_key=SERIES_REVENUE).exists():
                    ForecastPoint.objects.filter(series_key=SERIES_REVENUE, date__gte=date.today()).delete()
                for d, y, yl, yu in zip(options.labels, options.yhat, options.yhat_lower or [], options.yhat_upper or []):
                    ForecastPoint.objects.update_or_create(
                        series_key=SERIES_REVENUE,
                        date=d,
                        defaults={'yhat': y, 'yhat_lower': yl if yl is not None else y, 'yhat_upper': yu if yu is not None else y}
                    )

    @transaction.atomic
    def recompute_next_actions(self):
        NextActionForecast.objects.all().delete()
        for s in suggest_next_actions():
            NextActionForecast.objects.update_or_create(
                deal_id=s.deal_id,
                suggested_action=s.suggested_action,
                defaults={'probability': s.probability}
            )

    @transaction.atomic
    def recompute_client_next_actions(self):
        ClientNextActionForecast.objects.all().delete()
        for s in suggest_next_actions_for_clients():
            ClientNextActionForecast.objects.update_or_create(
                company_id=s.company_id,
                suggested_action=s.suggested_action,
                defaults={'probability': s.probability}
            )
