from django.http import JsonResponse
from django.utils import timezone
from django.contrib.admin.models import LogEntry
from django.db.models import Sum


def dashboard_stats_api(request):
    """Return live statistics for the admin dashboard."""
    try:
        from crm.models import Lead, Deal, Company
        from crm.models.payment import Payment

        now = timezone.now()
        current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        active_leads = Lead.objects.filter(closing_reason__isnull=True, deal__isnull=True).count()
        open_deals = Deal.objects.exclude(stage__success=True).count()
        companies = Company.objects.count()
        monthly_revenue = Payment.objects.filter(creation_date__gte=current_month).aggregate(total=Sum('amount'))['total'] or 0

        return JsonResponse({
            'leads_count': active_leads,
            'deals_count': open_deals,
            'companies_count': companies,
            'monthly_revenue': float(monthly_revenue),
        })
    except Exception:
        # Graceful fallback to zeros to avoid breaking UI
        return JsonResponse({
            'leads_count': 0,
            'deals_count': 0,
            'companies_count': 0,
            'monthly_revenue': 0.0,
        })


def recent_actions_api(request):
    """Return recent admin actions for the dashboard."""
    try:
        logs = LogEntry.objects.select_related('content_type', 'user').order_by('-action_time')[:10]
        items = []
        now = timezone.now()
        for log in logs:
            if log.is_addition():
                kind = 'add'
            elif log.is_change():
                kind = 'change'
            else:
                kind = 'delete'

            td = now - log.action_time
            if td.days > 0:
                human = f"{td.days} дн. назад"
            elif td.seconds >= 3600:
                human = f"{td.seconds // 3600} ч. назад"
            elif td.seconds >= 60:
                human = f"{td.seconds // 60} мин. назад"
            else:
                human = "только что"

            items.append({
                'type': kind,
                'text': log.get_change_message() or f"{log.get_action_flag_display()} {log.content_type.name}: {log.object_repr}",
                'time': human,
                'user': (log.user.get_full_name() or log.user.username) if log.user_id else 'System',
            })
        return JsonResponse({'actions': items})
    except Exception:
        return JsonResponse({'actions': []})
