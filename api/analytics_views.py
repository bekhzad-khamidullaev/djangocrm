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


# ============================================================================
# PREDICTION & FORECASTING API ENDPOINTS
# ============================================================================

from rest_framework import viewsets, permissions
from rest_framework.decorators import action

from analytics.models import ForecastPoint, NextActionForecast, ClientNextActionForecast
from analytics.tasks import (
    predict_revenue_task, predict_leads_task, predict_clients_task,
    predict_next_actions_task, predict_client_actions_task, predict_all_task
)


@extend_schema(tags=['Analytics & Predictions'])
class PredictionViewSet(viewsets.ViewSet):
    """API endpoints for predictions and forecasting"""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'], url_path='revenue/predict')
    def predict_revenue(self, request):
        """Trigger revenue prediction task"""
        horizon_days = int(request.data.get('horizon_days', 30))
        run_async = request.data.get('async', True)
        
        if run_async:
            task = predict_revenue_task.delay(horizon_days)
            return Response({'status': 'started', 'task_id': task.id, 'horizon_days': horizon_days})
        return Response(predict_revenue_task(horizon_days))
    
    @action(detail=False, methods=['get'], url_path='revenue/forecast')
    def get_revenue_forecast(self, request):
        """Get revenue forecast data"""
        days = int(request.query_params.get('days', 30))
        forecasts = ForecastPoint.objects.filter(series_key='daily_revenue').order_by('date')[:days]
        data = [{'date': f.date.isoformat(), 'predicted': round(f.yhat, 2),
                 'lower': round(f.yhat_lower, 2) if f.yhat_lower else None,
                 'upper': round(f.yhat_upper, 2) if f.yhat_upper else None} for f in forecasts]
        return Response({'series': 'daily_revenue', 'count': len(data), 'forecasts': data})
    
    @action(detail=False, methods=['post'], url_path='leads/predict')
    def predict_leads(self, request):
        """Trigger leads prediction task"""
        horizon_days = int(request.data.get('horizon_days', 30))
        run_async = request.data.get('async', True)
        if run_async:
            task = predict_leads_task.delay(horizon_days)
            return Response({'status': 'started', 'task_id': task.id})
        return Response(predict_leads_task(horizon_days))
    
    @action(detail=False, methods=['get'], url_path='leads/forecast')
    def get_leads_forecast(self, request):
        """Get leads forecast data"""
        days = int(request.query_params.get('days', 30))
        forecasts = ForecastPoint.objects.filter(series_key='new_leads').order_by('date')[:days]
        data = [{'date': f.date.isoformat(), 'predicted': round(f.yhat, 2)} for f in forecasts]
        return Response({'series': 'new_leads', 'count': len(data), 'forecasts': data})
    
    @action(detail=False, methods=['post'], url_path='clients/predict')
    def predict_clients(self, request):
        """Trigger clients prediction task"""
        horizon_days = int(request.data.get('horizon_days', 30))
        run_async = request.data.get('async', True)
        if run_async:
            task = predict_clients_task.delay(horizon_days)
            return Response({'status': 'started', 'task_id': task.id})
        return Response(predict_clients_task(horizon_days))
    
    @action(detail=False, methods=['get'], url_path='clients/forecast')
    def get_clients_forecast(self, request):
        """Get clients forecast data"""
        days = int(request.query_params.get('days', 30))
        forecasts = ForecastPoint.objects.filter(series_key='new_clients').order_by('date')[:days]
        data = [{'date': f.date.isoformat(), 'predicted': round(f.yhat, 2)} for f in forecasts]
        return Response({'series': 'new_clients', 'count': len(data), 'forecasts': data})
    
    @action(detail=False, methods=['post'], url_path='next-actions/predict')
    def predict_next_actions(self, request):
        """Trigger next actions prediction for deals"""
        limit_per_stage = int(request.data.get('limit_per_stage', 5))
        run_async = request.data.get('async', True)
        if run_async:
            task = predict_next_actions_task.delay(limit_per_stage)
            return Response({'status': 'started', 'task_id': task.id})
        return Response(predict_next_actions_task(limit_per_stage))
    
    @action(detail=False, methods=['get'], url_path='next-actions/deals')
    def get_deal_next_actions(self, request):
        """Get predicted next actions for deals"""
        deal_id = request.query_params.get('deal_id')
        limit = int(request.query_params.get('limit', 50))
        queryset = NextActionForecast.objects.all()
        if deal_id:
            queryset = queryset.filter(deal_id=deal_id)
        queryset = queryset.order_by('-probability')[:limit]
        data = [{'deal_id': f.deal_id, 'action': f.suggested_action, 'probability': f.probability} for f in queryset]
        return Response({'count': len(data), 'predictions': data})
    
    @action(detail=False, methods=['post'], url_path='next-actions/clients/predict')
    def predict_client_actions(self, request):
        """Trigger next actions prediction for clients"""
        limit = int(request.data.get('limit', 200))
        run_async = request.data.get('async', True)
        if run_async:
            task = predict_client_actions_task.delay(limit)
            return Response({'status': 'started', 'task_id': task.id})
        return Response(predict_client_actions_task(limit))
    
    @action(detail=False, methods=['get'], url_path='next-actions/clients')
    def get_client_next_actions(self, request):
        """Get predicted next actions for clients"""
        company_id = request.query_params.get('company_id')
        limit = int(request.query_params.get('limit', 50))
        queryset = ClientNextActionForecast.objects.all()
        if company_id:
            queryset = queryset.filter(company_id=company_id)
        queryset = queryset.order_by('-probability')[:limit]
        data = [{'company_id': f.company_id, 'action': f.suggested_action, 'probability': f.probability} for f in queryset]
        return Response({'count': len(data), 'predictions': data})
    
    @action(detail=False, methods=['post'], url_path='predict-all')
    def predict_all(self, request):
        """Trigger all prediction tasks"""
        horizon_days = int(request.data.get('horizon_days', 30))
        run_async = request.data.get('async', True)
        if run_async:
            task = predict_all_task.delay(horizon_days)
            return Response({'status': 'started', 'task_id': task.id, 'horizon_days': horizon_days})
        return Response(predict_all_task(horizon_days))
    
    @action(detail=False, methods=['get'], url_path='status')
    def prediction_status(self, request):
        """Get overall prediction status"""
        return Response({
            'forecasts': {
                'revenue': {'count': ForecastPoint.objects.filter(series_key='daily_revenue').count()},
                'leads': {'count': ForecastPoint.objects.filter(series_key='new_leads').count()},
                'clients': {'count': ForecastPoint.objects.filter(series_key='new_clients').count()}
            },
            'action_predictions': {
                'deals': {'count': NextActionForecast.objects.count()},
                'clients': {'count': ClientNextActionForecast.objects.count()}
            }
        })
