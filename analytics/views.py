"""
Analytics Dashboard Views - Custom Built-in Dashboard
"""
from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth, TruncDay
from datetime import datetime, timedelta
from decimal import Decimal

from crm.models import Deal, Lead, Contact, Request
from django.contrib.auth.models import User
from common.models import Department
from analytics.utils.bi_helpers import get_cohort_data, get_forecast_data


@staff_member_required
def analytics_dashboard(request):
    """Main analytics dashboard view"""
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
    context = {
        'page_title': 'Analytics Dashboard',
        'dashboard_data': get_dashboard_data(period=period, owner_id=owner, department_id=department),
        'owners': list(owner_qs.values('id','first_name','last_name').order_by('first_name','last_name')),
        'departments': list(dept_qs.values('id','name').order_by('name')),
        'period': period,
        'owner': owner,
        'department': department,
    }
    return render(request, 'analytics/dashboard_admin.html', context)


@staff_member_required
def dashboard_api(request):
    """API endpoint for dashboard data"""
    period = request.GET.get('period', '30d')
    owner = request.GET.get('owner')
    department = request.GET.get('department')
    return JsonResponse(get_dashboard_data(period=period, owner_id=owner, department_id=department))


def get_dashboard_data(period='30d', owner_id=None, department_id=None):
    """Get all dashboard data with optional filters"""
    # Date ranges
    now = datetime.now()
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
    
    # Base filters
    owner_filter = {}
    if owner_id:
        owner_filter['owner_id'] = owner_id
    if department_id:
        owner_filter['department_id'] = department_id

    # Current period metrics
    current_deals = Deal.objects.filter(creation_date__gte=current_month_start, **owner_filter)
    current_won_deals = current_deals.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True))
    current_revenue = current_won_deals.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    current_leads = Lead.objects.filter(creation_date__gte=current_month_start, **owner_filter).count()
    
    # Previous period metrics
    prev_deals = Deal.objects.filter(creation_date__range=[prev_month_start, prev_month_end], **owner_filter)
    prev_won_deals = prev_deals.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True))
    prev_revenue = prev_won_deals.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
    prev_leads = Lead.objects.filter(creation_date__range=[prev_month_start, prev_month_end], **owner_filter).count()
    
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
    leads_30_days = Lead.objects.filter(creation_date__date__gte=last_30_days, **owner_filter).count()
    converted_leads = Lead.objects.filter(creation_date__date__gte=last_30_days, contact__isnull=False, **owner_filter).count()
    lead_conversion_rate = (converted_leads / leads_30_days * 100) if leads_30_days > 0 else 0
    
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
        'top_performers': {
            'by_deals': list(top_by_deals),
            'by_revenue': list(top_by_revenue),
            'month_name': current_month_start.strftime('%B %Y'),
        },
        'owner_breakdown': list(Deal.objects.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True), creation_date__gte=current_month_start, **owner_filter).values('owner__first_name','owner__last_name','owner_id').annotate(deals_count=Count('id'), total_revenue=Sum('amount')).order_by('-total_revenue')[:10]),
        'department_breakdown': list(Deal.objects.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True), creation_date__gte=current_month_start, **owner_filter).values('department__name','department_id').annotate(deals_count=Count('id'), total_revenue=Sum('amount')).order_by('-total_revenue')[:10]),
        'cohorts': get_cohort_data(owner_filter),
        'forecast': get_forecast_data(owner_filter),
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