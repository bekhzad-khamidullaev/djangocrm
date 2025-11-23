from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from django.db.models.functions import TruncDay, Coalesce
from django.db.models import Count, Sum, Q, F
from django.utils import timezone

try:
    # Prophet was renamed to 'prophet' (formerly fbprophet)
    from prophet import Prophet  # type: ignore
except Exception:  # pragma: no cover - allows project to run without prophet
    Prophet = None  # type: ignore

import pandas as pd  # type: ignore

from crm.models import Lead, Company, Deal
from marketing.models import CampaignRun


def forecast_daily_revenue(horizon_days: int = 30) -> Optional[SeriesForecast]:
    if not _ensure_prophet():
        return None
    # Aggregate daily revenue of won deals (win or conditional success); sum amount
    qs = (
        Deal.objects
        .filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True))
        .annotate(day=TruncDay('win_closing_date'))
        .values('day')
        .annotate(revenue=Sum('amount'))
        .order_by('day')
    )
    rows = [r for r in qs if r['day'] is not None]
    if not rows:
        # fallback to creation_date if win_closing_date absent
        qs2 = (
            Deal.objects
            .filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True))
            .annotate(day=TruncDay('creation_date'))
            .values('day')
            .annotate(revenue=Sum('amount'))
            .order_by('day')
        )
        rows = list(qs2)
        if not rows:
            return None
    start = rows[0]['day']
    end = rows[-1]['day']
    days = _date_range(start, end)
    rev_map = {r['day'].strftime('%Y-%m-%d'): float(r['revenue'] or 0) for r in rows}
    labels, values = _fill_series_map(days, rev_map)
    if len(values) < 7:
        return None
    df = pd.DataFrame({'ds': pd.to_datetime(labels), 'y': values})
    m = Prophet(seasonality_mode='additive', weekly_seasonality=True, daily_seasonality=False)
    m.fit(df)
    future = m.make_future_dataframe(periods=horizon_days, freq='D')
    fc = m.predict(future)
    tail = fc.tail(horizon_days)
    labels_fc = [d.strftime('%Y-%m-%d') for d in tail['ds']]
    return SeriesForecast(
        labels=labels_fc,
        yhat=[float(v) for v in tail['yhat']],
        yhat_lower=[float(v) for v in tail['yhat_lower']],
        yhat_upper=[float(v) for v in tail['yhat_upper']],
        history_labels=labels,
        history_values=values,
        meta={'series_key': 'revenue_daily'}
    )



@dataclass
class SeriesForecast:
    labels: List[str]
    yhat: List[float]
    yhat_lower: Optional[List[float]] = None
    yhat_upper: Optional[List[float]] = None
    history_labels: Optional[List[str]] = None
    history_values: Optional[List[float]] = None
    meta: Optional[Dict] = None
    labels: List[str]
    yhat: List[float]
    yhat_lower: Optional[List[float]] = None
    yhat_upper: Optional[List[float]] = None
    history_labels: Optional[List[str]] = None
    history_values: Optional[List[float]] = None


def _ensure_prophet() -> bool:
    return Prophet is not None


def _date_range(start: datetime, end: datetime) -> List[datetime]:
    days = []
    cur = start
    while cur.date() <= end.date():
        days.append(cur)
        cur += timedelta(days=1)
    return days


def _fill_series_map(dates: List[datetime], values_map: Dict[str, float]) -> Tuple[List[str], List[float]]:
    labels = [d.strftime('%Y-%m-%d') for d in dates]
    values = [float(values_map.get(lbl, 0)) for lbl in labels]
    return labels, values


def _aggregate_daily(model_qs, date_field: str = 'creation_date') -> Tuple[List[str], List[float]]:
    qs = (
        model_qs
        .annotate(day=TruncDay(date_field))
        .values('day')
        .annotate(c=Count('id'))
        .order_by('day')
    )
    rows = list(qs)
    if not rows:
        return [], []
    start = rows[0]['day']
    end = rows[-1]['day']
    days = _date_range(start, end)
    values_map = {r['day'].strftime('%Y-%m-%d'): float(r['c'] or 0) for r in rows}
    labels, values = _fill_series_map(days, values_map)
    return labels, values


def forecast_new_leads(horizon_days: int = 30) -> Optional[SeriesForecast]:
    """Prophet forecast for new leads per day."""
    if not _ensure_prophet():
        return None

    base_qs = Lead.objects.all()
    labels, values = _aggregate_daily(base_qs, 'creation_date')
    if len(values) < 7:  # minimal history
        return None

    df = pd.DataFrame({'ds': pd.to_datetime(labels), 'y': values})
    m = Prophet(seasonality_mode='additive', weekly_seasonality=True, daily_seasonality=False)
    m.fit(df)
    future = m.make_future_dataframe(periods=horizon_days, freq='D')
    fc = m.predict(future)
    tail = fc.tail(horizon_days)
    labels_fc = [d.strftime('%Y-%m-%d') for d in tail['ds']]
    return SeriesForecast(
        labels=labels_fc,
        yhat=[float(v) for v in tail['yhat']],
        yhat_lower=[float(v) for v in tail['yhat_lower']],
        yhat_upper=[float(v) for v in tail['yhat_upper']],
        history_labels=labels,
        history_values=values,
        meta={'series_key': 'leads_daily'}
    )


def _reach_series() -> Tuple[List[str], List[float]]:
    """Aggregate daily marketing reach from CampaignRun (sent or delivered)."""
    qs = (
        CampaignRun.objects
        .annotate(day=TruncDay('started_at'))
        .values('day')
        .annotate(sent_sum=Count('id'))  # fallback if quantities are 0; we will use delivered/sent fields if present
        .order_by('day')
    )
    # Prefer numeric volume from delivered>0 else sent>0 else 1 per run
    labels: List[str] = []
    vals: List[float] = []
    for r in qs:
        labels.append(r['day'].strftime('%Y-%m-%d'))
        # We do not have aggregation of delivered/sent in values() queryset here; fetch per-day sums with extra query
        day = r['day']
        day_runs = CampaignRun.objects.filter(started_at__date=day.date())
        delivered = sum(max(0, x.delivered) for x in day_runs)
        sent = sum(max(0, x.sent) for x in day_runs)
        vals.append(float(delivered or sent or len(day_runs)))
    return labels, vals


def forecast_new_clients_with_reach(horizon_days: int = 30) -> Optional[SeriesForecast]: 
    """
    Prophet forecast for new clients (companies created) with marketing reach as exogenous regressor.
    Uses CampaignRun daily delivered/sent as proxy for reach.
    """
    if not _ensure_prophet():
        return None

    labels_clients, values_clients = _aggregate_daily(Company.objects.all(), 'creation_date')
    if len(values_clients) < 7:
        return None

    labels_reach, values_reach = _reach_series()
    # Align by date; build a unified index
    all_dates = sorted(set(labels_clients) | set(labels_reach))
    clients_map = {d: 0.0 for d in all_dates}
    reach_map = {d: 0.0 for d in all_dates}
    clients_map.update({d: float(v) for d, v in zip(labels_clients, values_clients)})
    reach_map.update({d: float(v) for d, v in zip(labels_reach, values_reach)})

    df = pd.DataFrame({'ds': pd.to_datetime(all_dates), 'y': [clients_map[d] for d in all_dates], 'reach': [reach_map[d] for d in all_dates]})
    m = Prophet(seasonality_mode='additive', weekly_seasonality=True, daily_seasonality=False)
    m.add_regressor('reach')
    m.fit(df)

    future = m.make_future_dataframe(periods=horizon_days, freq='D')
    # For the regressor, extend with last known reach (or 0)
    last_reach = df['reach'].iloc[-1] if not df.empty else 0.0
    future = future.merge(pd.DataFrame({'ds': future['ds'], 'reach': last_reach}), on='ds', how='left')

    fc = m.predict(future)
    tail = fc.tail(horizon_days)
    labels_fc = [d.strftime('%Y-%m-%d') for d in tail['ds']]
    return SeriesForecast(
        labels=labels_fc,
        yhat=[float(v) for v in tail['yhat']],
        yhat_lower=[float(v) for v in tail['yhat_lower']],
        yhat_upper=[float(v) for v in tail['yhat_upper']],
        history_labels=all_dates,
        history_values=[float(clients_map[d]) for d in all_dates],
        meta={'series_key': 'clients_daily'}
    )
