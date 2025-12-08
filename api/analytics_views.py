"""
API endpoints for Analytics (computed statistics)
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import timedelta

from crm.models import Deal, Lead, Company, Contact


@extend_schema(tags=['Analytics'])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def analytics_overview(request):
    """Get overview analytics for dashboard"""
    user = request.user
    
    # Filter by user permissions
    if user.is_superuser:
        deals = Deal.objects.all()
        leads = Lead.objects.all()
        companies = Company.objects.all()
        contacts = Contact.objects.all()
    else:
        departments = user.groups.all()
        deals = Deal.objects.filter(Q(owner=user) | Q(co_owner=user))
        leads = Lead.objects.filter(Q(owner=user) | Q(department__in=departments))
        companies = Company.objects.filter(Q(owner=user) | Q(department__in=departments))
        contacts = Contact.objects.filter(Q(owner=user) | Q(department__in=departments))
    
    # Date range
    days = int(request.query_params.get('days', 30))
    date_from = timezone.now() - timedelta(days=days)
    
    return Response({
        'period_days': days,
        'deals': {
            'total': deals.count(),
            'active': deals.filter(active=True).count(),
            'total_amount': deals.aggregate(total=Sum('amount'))['total'] or 0,
        },
        'leads': {
            'total': leads.count(),
            'new': leads.filter(creation_date__gte=date_from).count(),
            'qualified': leads.filter(was_in_touch__isnull=False).count(),
        },
        'companies': {
            'total': companies.count(),
            'new': companies.filter(creation_date__gte=date_from).count(),
        },
        'contacts': {
            'total': contacts.count(),
            'new': contacts.filter(creation_date__gte=date_from).count(),
        },
    })
