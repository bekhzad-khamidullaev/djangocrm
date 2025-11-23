"""
Analytics Dashboard Views - Custom Built-in Dashboard
"""
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import JsonResponse
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth, TruncDay, ExtractHour, ExtractWeekDay
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal

from crm.models import Deal, Lead, Contact, Request
from django.contrib.auth.models import User
from common.models import Department
from analytics.utils.bi_helpers import get_cohort_data, get_forecast_data
from analytics.utils.forecasting import forecast_new_leads, forecast_new_clients_with_reach, forecast_daily_revenue
from analytics.utils.funnel_forecasting import suggest_next_actions
from analytics.dash_plugins.crm_analytics_plugins import (
    SalesOverviewPlugin,
    RevenueChartPlugin,
    LeadSourcesPlugin,
    SalesFunnelPlugin,
    TopPerformersPlugin,
    RecentActivityPlugin,
    ForecastsPlugin,
    RevenueForecastPlugin,
    DailyRevenueForecastPlugin,
)
from django.contrib.auth.models import User
from common.models import Department


@staff_member_required
def analytics_dashboard(request):
    """Main analytics dashboard view (Matplotlib-rendered images)"""
    from analytics.utils.mpl import to_img, plot_forecast
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np

    period = request.GET.get('period', '30d')
    owner = request.GET.get('owner')
    department = request.GET.get('department')

    # Restrict dropdowns by user permissions
    if request.user.is_superuser:
        dept_qs = Department.objects.all()
        owner_qs = User.objects.all()
    else:
        dept_qs = Department.objects.filter(id__in=request.user.groups.values('id'))
        owner_qs = User.objects.filter(groups__in=dept_qs).distinct()

    data = get_dashboard_data(period=period, owner_id=owner, department_id=department)

    # Build images
    revenue_chart_img = None
    rc = data.get('revenue_chart') or {}
    if rc.get('labels') and rc.get('data'):
        fig, ax = plt.subplots(figsize=(6,3))
        ax.plot(rc['labels'], rc['data'], label='Revenue', color='#10b981', marker='o')
        ax.legend(loc='lower center', ncol=2)
        ax.tick_params(axis='x', labelrotation=45)
        ax.set_title('Revenue by month (12m)')
        revenue_chart_img = to_img(fig)

    daily_trend_img = None
    dt = data.get('daily_trend') or {}
    if dt.get('labels') and (dt.get('leads') or dt.get('deals')):
        fig, ax = plt.subplots(figsize=(6,3))
        if dt.get('leads'):
            ax.plot(dt['labels'], dt['leads'], label='Leads', color='#3b82f6')
        if dt.get('deals'):
            ax.plot(dt['labels'], dt['deals'], label='Deals', color='#ef4444')
        ax.legend(loc='lower center', ncol=2)
        ax.tick_params(axis='x', labelrotation=45)
        ax.set_title('Daily trend')
        daily_trend_img = to_img(fig)

    stage_distribution_img = None
    sd = data.get('stage_distribution') or []
    if sd:
        labels = [x.get('stage__name') or '—' for x in sd]
        values = [x.get('count') or 0 for x in sd]
        fig, ax = plt.subplots(figsize=(5,5))
        ax.pie(values, labels=labels, autopct='%1.0f%%', startangle=140)
        ax.set_title('Stage distribution')
        stage_distribution_img = to_img(fig)

    lead_sources_img = None
    ls = (data.get('lead_sources') or {}).get('sources') or []
    if ls:
        labels = [x.get('lead_source__name') or '—' for x in ls]
        values = [x.get('count') or 0 for x in ls]
        fig, ax = plt.subplots(figsize=(5,5))
        ax.pie(values, labels=labels, autopct='%1.0f%%', startangle=140)
        ax.set_title('Lead sources')
        lead_sources_img = to_img(fig)

    requests_trend_img = None
    rt = data.get('requests_trend') or {}
    if rt.get('labels') and rt.get('data'):
        fig, ax = plt.subplots(figsize=(6,3))
        ax.plot(rt['labels'], rt['data'], label='Requests', color='#6366f1')
        ax.legend(loc='lower center', ncol=2)
        ax.tick_params(axis='x', labelrotation=45)
        ax.set_title('Requests trend')
        requests_trend_img = to_img(fig)

    funnel_img = None
    fn = (data.get('sales_funnel') or {}).get('stages') or []
    if fn:
        labels = [s.get('stage__name') or s.get('name') or '—' for s in fn]
        counts = [s.get('count') or 0 for s in fn]
        fig, ax = plt.subplots(figsize=(6,3))
        ax.bar(labels, counts, color='#3b82f6')
        ax.tick_params(axis='x', labelrotation=45)
        ax.set_title('Sales funnel (deal count)')
        funnel_img = to_img(fig)

    department_breakdown_img = None
    db = data.get('department_breakdown') or []
    if db:
        labels = [x.get('department__name') or '—' for x in db]
        values = [float(x.get('total_revenue') or 0) for x in db]
        fig, ax = plt.subplots(figsize=(6,3))
        ax.bar(labels, values, color='#14b8a6')
        ax.tick_params(axis='x', labelrotation=45)
        ax.set_title('Department revenue (current month)')
        department_breakdown_img = to_img(fig)

    owner_workload_img = None
    ow = data.get('owner_workload') or []
    if ow:
        labels = [x.get('name') or '—' for x in ow]
        created = [x.get('created') or 0 for x in ow]
        won = [x.get('won') or 0 for x in ow]
        idx = np.arange(len(labels)); width = 0.35
        fig, ax = plt.subplots(figsize=(6,3))
        ax.bar(idx - width/2, created, width, label='Created', color='#60a5fa')
        ax.bar(idx + width/2, won, width, label='Won', color='#10b981')
        ax.set_xticks(idx)
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.legend(loc='lower center', ncol=2)
        ax.set_title('Owner workload (current month)')
        owner_workload_img = to_img(fig)

    owner_breakdown_img = None
    ob = data.get('owner_breakdown') or []
    if ob:
        labels = ['{} {}'.format(x.get('owner__first_name') or '', x.get('owner__last_name') or '').strip() or '—' for x in ob]
        values = [float(x.get('total_revenue') or 0) for x in ob]
        fig, ax = plt.subplots(figsize=(6,3))
        ax.bar(labels, values, color='#14b8a6')
        ax.tick_params(axis='x', labelrotation=45)
        ax.set_title('Owner revenue (current month)')
        owner_breakdown_img = to_img(fig)

    # Forecast images (optionally duplicated on admin dashboard)
    revenue_forecast_img = None
    rf = data.get('forecast') or {}
    if rf.get('labels') and rf.get('data'):
        fig, ax = plt.subplots(figsize=(6,3))
        ax.plot(rf['labels'], rf['data'], label='Revenue forecast', color='#10b981', linestyle='--', marker='o')
        ax.legend(loc='lower center', ncol=2)
        ax.tick_params(axis='x', labelrotation=45)
        ax.set_title('Revenue forecast (3 months)')
        revenue_forecast_img = to_img(fig)

    lead_forecast_img = None
    lf = data.get('lead_forecast') or {}
    if lf:
        h = lf.get('history') or {}
        lead_forecast_img = plot_forecast(h.get('labels'), h.get('values'), lf.get('labels'), lf.get('yhat'), lf.get('yhat_lower'), lf.get('yhat_upper'), '#22c55e', 'Lead forecast (30d)')

    client_forecast_img = None
    cf = data.get('client_forecast') or {}
    if cf:
        h = cf.get('history') or {}
        client_forecast_img = plot_forecast(h.get('labels'), h.get('values'), cf.get('labels'), cf.get('yhat'), cf.get('yhat_lower'), cf.get('yhat_upper'), '#0ea5e9', 'New clients forecast (30d)')

    context = {
        'page_title': 'Analytics Dashboard',
        'owners': list(owner_qs.values('id','first_name','last_name').order_by('first_name','last_name')),
        'departments': list(dept_qs.values('id','name').order_by('name')),
        'period': period,
        'owner': owner,
        'department': department,
        # Image context
        'revenue_chart_img': revenue_chart_img,
        'daily_trend_img': daily_trend_img,
        'stage_distribution_img': stage_distribution_img,
        'lead_sources_img': lead_sources_img,
        'requests_trend_img': requests_trend_img,
        'funnel_img': funnel_img,
        'department_breakdown_img': department_breakdown_img,
        'owner_workload_img': owner_workload_img,
        'owner_breakdown_img': owner_breakdown_img,
        'revenue_forecast_img': revenue_forecast_img,
        'lead_forecast_img': lead_forecast_img,
        'client_forecast_img': client_forecast_img,
        # Non-image data still used by tables/heatmap
        'dashboard_data': data,
    }
    return render(request, 'analytics/dashboard_admin.html', context)


@staff_member_required
def dashboard_api(request):
    """API endpoint for dashboard data"""
    period = request.GET.get('period', '30d')
    owner = request.GET.get('owner')
    department = request.GET.get('department')
    return JsonResponse(get_dashboard_data(period=period, owner_id=owner, department_id=department))

@staff_member_required
def analytics_forecasts(request):
    period = request.GET.get('period', '30d')
    owner = request.GET.get('owner')
    department = request.GET.get('department')
    # Reuse same lists for filters as main dashboard
    if request.user.is_superuser:
        dept_qs = Department.objects.all()
        owner_qs = User.objects.all()
    else:
        dept_qs = Department.objects.filter(id__in=request.user.groups.values('id'))
        owner_qs = User.objects.filter(groups__in=dept_qs).distinct()
    # Build payload focused on forecasts
    data = get_dashboard_data(period=period, owner_id=owner, department_id=department)
    context = {
        'page_title': 'Forecasts Dashboard',
        'forecasts_data': {
            'forecast': data.get('forecast'),
            'lead_forecast': data.get('lead_forecast'),
            'client_forecast': data.get('client_forecast'),
            'funnel_next_actions': data.get('funnel_next_actions'),
            'client_next_actions': data.get('client_next_actions'),
        },
        'owners': list(owner_qs.values('id','first_name','last_name').order_by('first_name','last_name')),
        'departments': list(dept_qs.values('id','name').order_by('name')),
        'period': period,
        'owner': owner,
        'department': department,
    }
    return render(request, 'analytics/forecasts_dashboard.html', context)


@staff_member_required
def forecasts_api(request):
    period = request.GET.get('period', '30d')
    owner = request.GET.get('owner')
    department = request.GET.get('department')
    data = get_dashboard_data(period=period, owner_id=owner, department_id=department)
    return JsonResponse({
        'forecast': data.get('forecast'),
        'lead_forecast': data.get('lead_forecast'),
        'client_forecast': data.get('client_forecast'),
        'funnel_next_actions': data.get('funnel_next_actions'),
        'client_next_actions': data.get('client_next_actions'),
    })


def get_dashboard_data(period='30d', owner_id=None, department_id=None):
    """Get all dashboard data with optional filters"""
    # Date ranges
    now = timezone.now()
    period_map = {
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
        '90d': timedelta(days=90),
        '12m': timedelta(days=365),
    }
    window = period_map.get(period, timedelta(days=30))
    current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_30_days = now - window
    
    # Previous month
    if now.month == 1:
        prev_month_start = now.replace(year=now.year-1, month=12, day=1)
        prev_month_end = current_month_start - timedelta(days=1)
    else:
        prev_month_start = now.replace(month=now.month-1, day=1)
        prev_month_end = current_month_start - timedelta(days=1)
    
    # Base filters with safe parsing of IDs (handle 'all' or invalid values)
    def _to_int_or_none(val):
        if val in (None, '', 'all'):
            return None
        try:
            return int(val)
        except (TypeError, ValueError):
            return None

    owner_id_int = _to_int_or_none(owner_id)
    department_id_int = _to_int_or_none(department_id)

    owner_filter = {}
    if owner_id_int is not None:
        owner_filter['owner_id'] = owner_id_int
    if department_id_int is not None:
        owner_filter['department_id'] = department_id_int

    # Current period metrics
    current_deals = Deal.objects.filter(creation_date__gte=current_month_start, **owner_filter)
    current_won_deals = current_deals.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True))
    current_revenue = current_won_deals.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    current_leads = Lead.objects.filter(creation_date__gte=current_month_start, **owner_filter).count()
    
    # Previous period metrics
    prev_deals = Deal.objects.filter(creation_date__date__range=[prev_month_start, prev_month_end], **owner_filter)
    prev_won_deals = prev_deals.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True))
    prev_revenue = prev_won_deals.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    prev_leads = Lead.objects.filter(creation_date__date__range=[prev_month_start, prev_month_end], **owner_filter).count()
    
    # Calculate changes
    def calculate_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return ((current - previous) / previous) * 100
    
    # Last 30 days overview
    deals_30_days = Deal.objects.filter(creation_date__date__gte=last_30_days, **owner_filter)
    total_deals = deals_30_days.count()
    won_deals = deals_30_days.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True)).count()
    lost_deals = deals_30_days.filter(closing_reason__isnull=False, closing_reason__success_reason=False).count()
    total_revenue_30 = deals_30_days.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True)).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    
    # Conversion rates
    win_rate = (won_deals / total_deals * 100) if total_deals > 0 else 0
    leads_30_days_qs = Lead.objects.filter(creation_date__date__gte=last_30_days, **owner_filter)
    leads_30_days = leads_30_days_qs.count()
    converted_leads = leads_30_days_qs.filter(contact__isnull=False).count()
    lead_conversion_rate = (converted_leads / leads_30_days * 100) if leads_30_days > 0 else 0

    # Daily trend for last period window (leads vs deals)
    def _fill_daily_series(values_dict, days):
        return [values_dict.get(d.strftime('%Y-%m-%d'), 0) for d in days]
    days_range = [ (last_30_days + timedelta(days=i)).date() for i in range((now.date() - last_30_days.date()).days + 1) ]
    day_labels = [ d.strftime('%Y-%m-%d') for d in days_range ]
    deals_daily = (deals_30_days
        .annotate(day=TruncDay('creation_date'))
        .values('day')
        .annotate(c=Count('id'))
        .order_by('day'))
    leads_daily = (leads_30_days_qs
        .annotate(day=TruncDay('creation_date'))
        .values('day')
        .annotate(c=Count('id'))
        .order_by('day'))
    deals_map = { x['day'].strftime('%Y-%m-%d'): x['c'] for x in deals_daily }
    leads_map = { x['day'].strftime('%Y-%m-%d'): x['c'] for x in leads_daily }
    daily_trend = {
        'labels': day_labels,
        'deals': _fill_daily_series(deals_map, days_range),
        'leads': _fill_daily_series(leads_map, days_range),
    }

    # Stage distribution (current month)
    stage_distribution = list(
        Deal.objects.filter(creation_date__gte=current_month_start, **owner_filter)
        .values('stage__name')
        .annotate(count=Count('id'), value=Sum('amount'))
        .order_by('-count')
    )

    # Requests volume (last period window)
    requests_daily_qs = Request.objects.filter(creation_date__date__gte=last_30_days, **owner_filter)
    requests_daily = (requests_daily_qs
        .annotate(day=TruncDay('creation_date'))
        .values('day')
        .annotate(c=Count('id'))
        .order_by('day'))
    requests_map = { x['day'].strftime('%Y-%m-%d'): x['c'] for x in requests_daily }
    requests_trend = _fill_daily_series(requests_map, days_range)

    # Activity heatmap (weekday x hour) combined for Deals + Leads + Requests
    def activity_matrix(qs, label):
        return list(
            qs.annotate(wd=ExtractWeekDay('creation_date'), hr=ExtractHour('creation_date'))
              .values('wd','hr').annotate(c=Count('id')).order_by('wd','hr')
        )
    deals_act = activity_matrix(Deal.objects.filter(creation_date__date__gte=last_30_days, **owner_filter), 'deals')
    leads_act = activity_matrix(Lead.objects.filter(creation_date__date__gte=last_30_days, **owner_filter), 'leads')
    requests_act = activity_matrix(Request.objects.filter(creation_date__date__gte=last_30_days, **owner_filter), 'requests')

    # Django ExtractWeekDay: 1=Sunday..7=Saturday; we'll map to 0..6 Mon..Sun
    def to_index(wd):
        # convert Sun..Sat (1..7) to Mon..Sun (0..6)
        return (wd + 5) % 7
    heatmap = [[0 for _ in range(24)] for _ in range(7)]
    for row in deals_act + leads_act + requests_act:
        wd = to_index(row['wd'] or 1)
        hr = row['hr'] or 0
        if 0 <= wd < 7 and 0 <= hr < 24:
            heatmap[wd][hr] += row['c']
    activity_heatmap = {
        'weekdays': ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'],
        'hours': [f"{h:02d}:00" for h in range(24)],
        'matrix': heatmap,
    }

    # Owner workload vs performance (current month)
    owners_created = list(
        Deal.objects.filter(creation_date__gte=current_month_start, **owner_filter)
        .values('owner_id','owner__first_name','owner__last_name')
        .annotate(created=Count('id'))
    )
    owners_won = list(
        Deal.objects.filter(creation_date__gte=current_month_start, **owner_filter)
        .filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True))
        .values('owner_id')
        .annotate(won=Count('id'))
    )
    won_map = { x['owner_id']: x['won'] for x in owners_won }
    owner_workload = [
        {
            'owner_id': o['owner_id'],
            'name': ' '.join(filter(None,[o['owner__first_name'], o['owner__last_name']])) or '—',
            'created': o['created'],
            'won': won_map.get(o['owner_id'], 0)
        } for o in owners_created
    ]
    
    # Monthly revenue chart (last 12 months)
    year_ago = now - timedelta(days=365)
    monthly_revenue = Deal.objects.filter(
        creation_date__date__gte=year_ago,
        **owner_filter
    ).filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True)
    ).annotate(
        month=TruncMonth('creation_date')
    ).values('month').annotate(
        revenue=Sum('amount')
    ).order_by('month')
    
    # Lead sources
    lead_sources = Lead.objects.filter(**owner_filter).values('lead_source__name').annotate(
        count=Count('id'),
        converted=Count('id', filter=Q(contact__isnull=False))
    ).order_by('-count')[:10]
    
    # Sales funnel
    funnel_data = Deal.objects.filter(**owner_filter).values('stage__name').annotate(
        count=Count('id'),
        total_value=Sum('amount')
    ).order_by('stage__index_number')
    
    # Top performers (current month)
    top_by_deals = Deal.objects.filter(
        Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True),
        creation_date__gte=current_month_start,
        **owner_filter
    ).values('owner__first_name', 'owner__last_name').annotate(
        deals_count=Count('id'),
        total_revenue=Sum('amount')
    ).order_by('-deals_count')[:5]
    
    top_by_revenue = Deal.objects.filter(
        Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True),
        creation_date__gte=current_month_start,
        **owner_filter
    ).values('owner__first_name', 'owner__last_name').annotate(
        deals_count=Count('id'),
        total_revenue=Sum('amount')
    ).order_by('-total_revenue')[:5]
    
    # Recent activity
    recent_deals = Deal.objects.select_related('owner', 'contact', 'company').filter(**owner_filter).order_by('-creation_date')[:10]
    recent_leads = Lead.objects.select_related('owner', 'lead_source').filter(**owner_filter).order_by('-creation_date')[:10]
    recent_requests = Request.objects.select_related('owner', 'contact').filter(**owner_filter).order_by('-creation_date')[:10]
    
    return {
        'filters': {
            'period': period,
            'owner_id': owner_id,
            'department_id': department_id,
        },
        'sales_overview': {
            'total_revenue': float(total_revenue_30),
            'total_deals': total_deals,
            'won_deals': won_deals,
            'lost_deals': lost_deals,
            'win_rate': round(win_rate, 1),
            'leads_count': leads_30_days,
            'converted_leads': converted_leads,
            'lead_conversion_rate': round(lead_conversion_rate, 1),
            'period_start': last_30_days.strftime('%Y-%m-%d'),
            'period_end': now.strftime('%Y-%m-%d'),
        },
        'kpi_metrics': {
            'current_revenue': float(current_revenue),
            'current_deals': current_won_deals.count(),
            'current_leads': current_leads,
            'revenue_change': round(calculate_change(float(current_revenue), float(prev_revenue)), 1),
            'deals_change': round(calculate_change(current_won_deals.count(), prev_won_deals.count()), 1),
            'leads_change': round(calculate_change(current_leads, prev_leads), 1),
            'current_month': current_month_start.strftime('%B %Y'),
            'previous_month': prev_month_start.strftime('%B %Y'),
        },
        'daily_trend': daily_trend,
        'stage_distribution': stage_distribution,
        'requests_trend': requests_trend,
        'owner_workload': owner_workload,
        'revenue_chart': {
            'labels': [item['month'].strftime('%b %Y') for item in monthly_revenue],
            'data': [float(item['revenue'] or 0) for item in monthly_revenue],
        },
        'lead_sources': {
            'sources': list(lead_sources),
            'total_leads': sum(item['count'] for item in lead_sources),
            'total_converted': sum(item['converted'] for item in lead_sources),
        },
        'sales_funnel': {
            'stages': list(funnel_data),
            'total_deals': Deal.objects.filter(**owner_filter).count(),
            'total_value': float(Deal.objects.filter(**owner_filter).aggregate(Sum('amount'))['amount__sum'] or 0),
        },
        'requests_trend': {'labels': day_labels, 'data': requests_trend},
        'activity_heatmap': activity_heatmap,
        'top_performers': {
            'by_deals': list(top_by_deals),
            'by_revenue': list(top_by_revenue),
            'month_name': current_month_start.strftime('%B %Y'),
        },
        'owner_breakdown': list(Deal.objects.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True), creation_date__gte=current_month_start, **owner_filter).values('owner__first_name','owner__last_name','owner_id').annotate(deals_count=Count('id'), total_revenue=Sum('amount')).order_by('-total_revenue')[:10]),
        'department_breakdown': list(Deal.objects.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True), creation_date__gte=current_month_start, **owner_filter).values('department__name','department_id').annotate(deals_count=Count('id'), total_revenue=Sum('amount')).order_by('-total_revenue')[:10]),
        'cohorts': get_cohort_data(owner_filter),
        'forecast': get_forecast_data(owner_filter),
        'lead_forecast': (lambda f: None if f is None else {
            'labels': f.labels, 'yhat': f.yhat, 'yhat_lower': f.yhat_lower, 'yhat_upper': f.yhat_upper,
            'history': {'labels': f.history_labels, 'values': f.history_values}
        })(forecast_new_leads()),
        'revenue_daily_forecast': (lambda f: None if f is None else {
            'labels': f.labels, 'yhat': f.yhat, 'yhat_lower': f.yhat_lower, 'yhat_upper': f.yhat_upper,
            'history': {'labels': f.history_labels, 'values': f.history_values}
        })(forecast_daily_revenue()),
        'client_forecast': (lambda f: None if f is None else {
            'labels': f.labels, 'yhat': f.yhat, 'yhat_lower': f.yhat_lower, 'yhat_upper': f.yhat_upper,
            'history': {'labels': f.history_labels, 'values': f.history_values}
        })(forecast_new_clients_with_reach()),
        'funnel_next_actions': [
            {'deal_id': x.deal_id, 'suggested_action': x.suggested_action, 'probability': x.probability}
            for x in suggest_next_actions()
        ],
        'client_next_actions': [
            {'company_id': x.company_id, 'suggested_action': x.suggested_action, 'probability': x.probability}
            for x in (lambda: __import__('analytics.utils.funnel_forecasting', fromlist=['suggest_next_actions_for_clients']).suggest_next_actions_for_clients())()
        ],
        'recent_activity': {
            'deals': [
                {
                    'id': deal.id,
                    'name': deal.name or f'Deal #{deal.id}',
                    'amount': float(deal.amount or 0),
                    'contact': deal.contact.full_name if deal.contact else None,
                    'company': deal.company.full_name if deal.company else None,
                    'owner': f'{deal.owner.first_name} {deal.owner.last_name}',
                    'stage': deal.stage.name if deal.stage else 'New',
                    'creation_date': deal.creation_date.isoformat(),
                }
                for deal in recent_deals
            ],
            'leads': [
                {
                    'id': lead.id,
                    'name': lead.full_name or f'Lead #{lead.id}',
                    'company': lead.company_name,
                    'email': lead.email,
                    'phone': lead.phone,
                    'owner': f'{lead.owner.first_name} {lead.owner.last_name}' if lead.owner else None,
                    'source': lead.lead_source.name if lead.lead_source else None,
                    'disqualified': lead.disqualified,
                    'was_in_touch': lead.was_in_touch,
                    'creation_date': lead.creation_date.isoformat(),
                }
                for lead in recent_leads
            ],
            'requests': [
                {
                    'id': request.id,
                    'subject': (getattr(request, 'request_for', '') or getattr(request, 'description', '') or f'Request #{request.id}'),
                    'contact': request.contact.full_name if request.contact else None,
                    'owner': f'{request.owner.first_name} {request.owner.last_name}' if request.owner else None,
                    'creation_date': request.creation_date.isoformat(),
                }
                for request in recent_requests
            ],
        },
    }