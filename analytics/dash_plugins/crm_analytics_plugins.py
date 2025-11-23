"""
CRM Analytics Dashboard Plugins for django-dash
"""
from dash.base import BaseDashboardPlugin
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Sum, Q
from django.db.models.functions import TruncMonth, TruncWeek, TruncDay
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal
import io
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from analytics.utils.forecasting import forecast_new_leads, forecast_new_clients_with_reach
from analytics.utils.funnel_forecasting import suggest_next_actions
import json
from analytics.utils.mpl import to_img, plot_forecast

from crm.models import Deal, Lead, Contact, Request
from analytics.models import IncomeStat, DealStat, LeadSourceStat
# helper fallbacks if not available
from datetime import date

def get_quarter_start(ref=None):
    ref = ref or date.today()
    q = (ref.month - 1) // 3
    start_month = q * 3 + 1
    return date(ref.year, start_month, 1)

def get_quarter_end(ref=None):
    ref = ref or date.today()
    q = (ref.month - 1) // 3
    end_month = q * 3 + 3
    # naive end = first day of next month - 1
    if end_month == 12:
        return date(ref.year, 12, 31)
    from datetime import timedelta
    return date(ref.year, end_month + 1, 1) - timedelta(days=1)


class SalesOverviewPlugin(BaseDashboardPlugin):
    """Sales Overview Dashboard Plugin"""
    
    name = 'sales_overview'
    title = _('Sales Overview')
    description = _('Key sales metrics and KPIs')
    category = _('Analytics')
    
    def process(self, request, **kwargs):
        """Process the plugin data"""
        # Get date range (last 30 days by default)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        # Sales metrics
        deals_qs = Deal.objects.filter(
            creation_date__date__range=[start_date, end_date]
        )
        
        total_deals = deals_qs.count()
        won_deals = deals_qs.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True)).count()
        lost_deals = deals_qs.filter(closing_reason__isnull=False, closing_reason__success_reason=False).count()
        
        total_revenue = deals_qs.filter(
            Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True)
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')
        
        # Conversion rates
        win_rate = (won_deals / total_deals * 100) if total_deals > 0 else 0
        
        # Lead metrics
        leads_count = Lead.objects.filter(
            creation_date__date__range=[start_date, end_date]
        ).count()
        
        converted_leads = Lead.objects.filter(
            creation_date__date__range=[start_date, end_date],
            contact__isnull=False
        ).count()
        
        lead_conversion_rate = (converted_leads / leads_count * 100) if leads_count > 0 else 0
        
        context = {
            'total_deals': total_deals,
            'won_deals': won_deals,
            'lost_deals': lost_deals,
            'total_revenue': total_revenue,
            'win_rate': round(win_rate, 1),
            'leads_count': leads_count,
            'converted_leads': converted_leads,
            'lead_conversion_rate': round(lead_conversion_rate, 1),
            'period_start': start_date,
            'period_end': end_date,
        }
        
        return render_to_string('analytics/dash/sales_overview.html', context)


class RevenueChartPlugin(BaseDashboardPlugin):
    name = 'revenue_chart'
    title = _('Revenue Chart')
    description = _('Monthly revenue trends')
    category = _('Analytics')
    
    def _plot(self, labels, values):
        fig, ax = plt.subplots(figsize=(6, 3))
        if labels and values:
            ax.plot(labels, values, label='Revenue', color='#36A2EB', linestyle='-', marker='o')
        ax.set_title('Revenue (last 12 months)')
        ax.tick_params(axis='x', labelrotation=45)
        ax.legend(loc='lower center', ncol=2)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120)
        plt.close(fig)
        buf.seek(0)
        return 'data:image/png;base64,' + base64.b64encode(buf.read()).decode('ascii')

    def process(self, request, **kwargs):
        end_date = timezone.now().date()
        start_date = end_date.replace(day=1) - timedelta(days=365)
        monthly_revenue = Deal.objects.filter(
            creation_date__date__range=[start_date, end_date]
        ).filter(
            Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True)
        ).annotate(
            month=TruncMonth('creation_date')
        ).values('month').annotate(
            revenue=Sum('amount')
        ).order_by('month')
        labels = [item['month'].strftime('%b %Y') for item in monthly_revenue]
        values = [float(item['revenue'] or 0) for item in monthly_revenue]
        context = {
            'img': self._plot(labels, values) if labels else None,
        }
        return render_to_string('analytics/dash/revenue_chart.html', context)
    # Matplotlib version implemented above


class LeadSourcesPlugin(BaseDashboardPlugin):
    name = 'lead_sources'
    title = _('Lead Sources')
    description = _('Lead distribution by sources (Matplotlib)')
    category = _('Analytics')

    def _plot(self, labels, total, converted):
        fig, ax = plt.subplots(figsize=(6, 3))
        x = range(len(labels))
        ax.bar(x, total, width=0.4, label='Total', color='#3b82f6')
        ax.bar([i+0.4 for i in x], converted, width=0.4, label='Converted', color='#10b981')
        ax.set_xticks([i+0.2 for i in x])
        ax.set_xticklabels(labels, rotation=45, ha='right')
        ax.set_title('Lead sources')
        ax.legend(loc='lower center', ncol=2)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120)
        plt.close(fig)
        buf.seek(0)
        return 'data:image/png;base64,' + base64.b64encode(buf.read()).decode('ascii')

    def process(self, request, **kwargs):
        lead_sources = Lead.objects.values('lead_source__name').annotate(
            count=Count('id'),
            converted=Count('id', filter=Q(contact__isnull=False))
        ).order_by('-count')[:10]
        labels = [(s['lead_source__name'] or 'Unknown') for s in lead_sources]
        total = [s['count'] for s in lead_sources]
        converted = [s['converted'] for s in lead_sources]
        total_leads = sum(total)
        total_converted = sum(converted)
        conversion_rate = (total_converted / total_leads * 100) if total_leads > 0 else 0
        context = {
            'img': self._plot(labels, total, converted) if labels else None,
            'total_leads': total_leads,
            'total_converted': total_converted,
            'conversion_rate': round(conversion_rate, 1),
            'sources_data': lead_sources
        }
        return render_to_string('analytics/dash/lead_sources.html', context)


class SalesFunnelPlugin(BaseDashboardPlugin):
    """Sales Funnel Analysis Plugin"""
    
    name = 'sales_funnel'
    title = _('Sales Funnel')
    description = _('Deal progression through sales stages')
    category = _('Analytics')
    
    def process(self, request, **kwargs):
        """Process sales funnel data"""
        # Get deals by stage
        funnel_data = Deal.objects.values(
            'stage__title'
        ).annotate(
            count=Count('id'),
            total_value=Sum('amount')
        ).order_by('stage__index')
        
        # Calculate funnel metrics
        total_deals = Deal.objects.count()
        total_value = Deal.objects.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        
        funnel_stages = []
        for i, stage in enumerate(funnel_data):
            stage_name = stage['stage__title'] or f'Stage {i+1}'
            stage_count = stage['count']
            stage_value = stage['total_value'] or Decimal('0')
            
            # Calculate percentages
            count_percentage = (stage_count / total_deals * 100) if total_deals > 0 else 0
            value_percentage = (stage_value / total_value * 100) if total_value > 0 else 0
            
            funnel_stages.append({
                'name': stage_name,
                'count': stage_count,
                'value': stage_value,
                'count_percentage': round(count_percentage, 1),
                'value_percentage': round(value_percentage, 1),
            })
        
        context = {
            'funnel_stages': funnel_stages,
            'total_deals': total_deals,
            'total_value': total_value
        }
        
        return render_to_string('analytics/dash/sales_funnel.html', context)


class TopPerformersPlugin(BaseDashboardPlugin):
    """Top Performers Plugin"""
    
    name = 'top_performers'
    title = _('Top Performers')
    description = _('Top performing sales representatives')
    category = _('Analytics')
    
    def process(self, request, **kwargs):
        """Process top performers data"""
        # Get current month start
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Top performers by deals won
        top_by_deals = Deal.objects.filter(
            stage__title__icontains='won',
            creation_date__gte=month_start
        ).values(
            'owner__first_name', 
            'owner__last_name'
        ).annotate(
            deals_count=Count('id'),
            total_revenue=Sum('amount')
        ).order_by('-deals_count')[:5]
        
        # Top performers by revenue
        top_by_revenue = Deal.objects.filter(
            stage__title__icontains='won',
            creation_date__gte=month_start
        ).values(
            'owner__first_name', 
            'owner__last_name'
        ).annotate(
            deals_count=Count('id'),
            total_revenue=Sum('amount')
        ).order_by('-total_revenue')[:5]
        
        context = {
            'top_by_deals': top_by_deals,
            'top_by_revenue': top_by_revenue,
            'month_name': now.strftime('%B %Y')
        }
        
        return render_to_string('analytics/dash/top_performers.html', context)


class RecentActivityPlugin(BaseDashboardPlugin):
    """Recent Activity Plugin"""
    
    name = 'recent_activity'
    title = _('Recent Activity')
    description = _('Latest CRM activities')
    category = _('Analytics')
    
    def process(self, request, **kwargs):
        """Process recent activity data"""
        # Recent deals (last 10)
        recent_deals = Deal.objects.select_related(
            'owner', 'contact', 'company'
        ).order_by('-creation_date')[:10]
        
        # Recent leads (last 10)
        recent_leads = Lead.objects.select_related(
            'owner', 'lead_source'
        ).order_by('-creation_date')[:10]
        
        # Recent requests (last 10)
        recent_requests = Request.objects.select_related(
            'owner', 'contact'
        ).order_by('-creation_date')[:10]
        
        context = {
            'recent_deals': recent_deals,
            'recent_leads': recent_leads,
            'recent_requests': recent_requests
        }
        
        return render_to_string('analytics/dash/recent_activity.html', context)


class ForecastsPlugin(BaseDashboardPlugin):
    name = 'forecasts'
    title = _('Forecasts')
    description = _('Leads and clients forecasts with suggested actions')
    category = _('Forecasts')

    # plotting delegated to analytics.utils.mpl.plot_forecast

    def process(self, request, **kwargs):
        lf = forecast_new_leads() or None
        cf = forecast_new_clients_with_reach() or None
        na = suggest_next_actions() or []
        lead_img = None
        client_img = None
        if lf:
            lead_img = plot_forecast(lf.history_labels or [], lf.history_values or [], lf.labels or [], lf.yhat or [], lf.yhat_lower, lf.yhat_upper, '#22c55e', 'Lead forecast (30d)')
        if cf:
            client_img = plot_forecast(cf.history_labels or [], cf.history_values or [], cf.labels or [], cf.yhat or [], cf.yhat_lower, cf.yhat_upper, '#0ea5e9', 'New clients forecast (30d)')
        context = {
            'lead_img': lead_img,
            'client_img': client_img,
            'next_actions': na[:20],
        }
        return render_to_string('analytics/dash/forecasts.html', context)


class KPIMetricsPlugin(BaseDashboardPlugin):
    name = 'kpi_metrics'
    title = _('KPI Metrics')
    description = _('Key Performance Indicators')
    category = _('Analytics')

    def process(self, request, **kwargs):
        from datetime import datetime
        now = datetime.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.month == 1:
            prev_month_start = now.replace(year=now.year-1, month=12, day=1)
            prev_month_end = current_month_start - timedelta(days=1)
        else:
            prev_month_start = now.replace(month=now.month-1, day=1)
            prev_month_end = current_month_start - timedelta(days=1)
        current_deals = Deal.objects.filter(creation_date__gte=current_month_start)
        current_won_deals = current_deals.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True))
        current_revenue = current_won_deals.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        current_leads = Lead.objects.filter(creation_date__gte=current_month_start).count()
        prev_deals = Deal.objects.filter(creation_date__range=[prev_month_start, prev_month_end])
        prev_won_deals = prev_deals.filter(Q(stage__success_stage=True) | Q(stage__conditional_success_stage=True))
        prev_revenue = prev_won_deals.aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
        prev_leads = Lead.objects.filter(creation_date__range=[prev_month_start, prev_month_end]).count()
        def change(cur, prev):
            if prev == 0:
                return 100 if cur > 0 else 0
            return ((cur - prev) / prev) * 100
        context = {
            'current_revenue': current_revenue,
            'current_deals': current_won_deals.count(),
            'current_leads': current_leads,
            'revenue_change': round(change(float(current_revenue), float(prev_revenue)), 1),
            'deals_change': round(change(current_won_deals.count(), prev_won_deals.count()), 1),
            'leads_change': round(change(current_leads, prev_leads), 1),
            'current_month': now.strftime('%B %Y'),
            'previous_month': prev_month_start.strftime('%B %Y'),
        }
        return render_to_string('analytics/dash/kpi_metrics.html', context)

class RevenueForecastPlugin(BaseDashboardPlugin):
    name = 'revenue_forecast'
    title = _('Revenue Forecast')
    description = _('Revenue forecast for next 3 months (Matplotlib)')
    category = _('Forecasts')

    def process(self, request, **kwargs):
        from analytics.utils.bi_helpers import get_forecast_data
        # owner_filter could be enriched from request/user context if needed
        owner_filter = {}
        data = get_forecast_data(owner_filter)
        img = None
        if data:
            labels = data.get('labels') or []
            values = data.get('data') or []
            fig, ax = plt.subplots(figsize=(6, 3))
            ax.plot(labels, values, label='Forecast', color='#10b981', linestyle='--', marker='o')
            ax.set_title('Revenue forecast (3 months)')
            ax.legend(loc='lower center', ncol=2)
            ax.tick_params(axis='x', labelrotation=45)
            img = to_img(fig)
        context = {'img': img}
        return render_to_string('analytics/dash/revenue_forecast.html', context)

class DailyRevenueForecastPlugin(BaseDashboardPlugin):
    name = 'daily_revenue_forecast'
    title = _('Daily Revenue Forecast')
    description = _('Daily revenue forecast for next 60 days (Matplotlib)')
    category = _('Forecasts')

    def process(self, request, **kwargs):
        from analytics.utils.forecasting import forecast_daily_revenue
        img = None
        f = forecast_daily_revenue()
        if f:
            img = plot_forecast(f.history_labels or [], f.history_values or [], f.labels or [], f.yhat or [], f.yhat_lower, f.yhat_upper, '#10b981', 'Daily revenue forecast (60d)')
        context = {'img': img}
        return render_to_string('analytics/dash/daily_revenue_forecast.html', context)

