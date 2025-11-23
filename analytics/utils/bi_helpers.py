from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth, TruncDay

from crm.models import Deal, Lead


def get_cohort_data(owner_filter: Dict) -> List[Dict]:
    """
    Build a simple cohort table for Leads by creation month.
    Retention is approximated as conversion to Contact (contact is not null).
    NOTE: Without a separate conversion timestamp, we can only mark M0 conversions.
    """
    qs = Lead.objects.filter(**owner_filter).annotate(cohort=TruncMonth('creation_date'))

    by_cohort = defaultdict(lambda: {'size': 0, 'converted_m0': 0})
    for row in qs.values('cohort', 'contact_id'):
        c = row['cohort']
        by_cohort[c]['size'] += 1
        if row['contact_id']:
            by_cohort[c]['converted_m0'] += 1

    out = []
    for cohort in sorted(by_cohort.keys()):
        data = by_cohort[cohort]
        size = data['size'] or 1
        m0 = round(data['converted_m0'] / size * 100, 1)
        out.append({
            'cohort': cohort.strftime('%Y-%m'),
            'size': data['size'],
            'retention': [m0, 0, 0, 0, 0, 0],
        })
    return out


def get_forecast_data(owner_filter: Dict) -> Optional[Dict]:
    """
    Forecast next 3 months revenue using Prophet if available, else return None.
    """
    try:
        from prophet import Prophet
        import pandas as pd  # type: ignore
    except Exception:
        return None

    # Build monthly revenue series (won or conditionally successful deals)
    qs = (
        Deal.objects.filter(**owner_filter)
        .filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True))
        .annotate(month=TruncMonth('creation_date'))
        .values('month')
        .annotate(revenue=Sum('amount'))
        .order_by('month')
    )
    rows = list(qs)
    if not rows:
        return None

    import pandas as pd  # type: ignore
    df = pd.DataFrame([
        {'ds': r['month'], 'y': float(r['revenue'] or 0)} for r in rows
    ])
    if len(df) < 3:
        return None

    m = Prophet(seasonality_mode='additive', weekly_seasonality=False, daily_seasonality=False)
    m.fit(df)
    future = m.make_future_dataframe(periods=3, freq='MS')
    forecast = m.predict(future)
    tail = forecast.tail(3)
    labels = [d.strftime('%b %Y') for d in tail['ds']]
    data = [round(float(v), 2) for v in tail['yhat']]
    return {'labels': labels, 'data': data}
