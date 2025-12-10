from __future__ import annotations
from celery import shared_task
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# FORECASTING & PREDICTION TASKS
# ============================================================================

@shared_task(name='analytics.recompute_forecasts', bind=True, max_retries=3)
def recompute_forecasts_task(self, horizon: int = 30):
    """
    Recompute all forecasts using Django management command
    
    Args:
        horizon: Number of days to forecast ahead
    """
    try:
        logger.info(f"Starting forecast recomputation with horizon={horizon} days")
        call_command('recompute_forecasts', horizon=horizon)
        logger.info("Forecast recomputation completed successfully")
        return {'success': True, 'horizon': horizon}
    except Exception as e:
        logger.error(f"Forecast recomputation failed: {str(e)}")
        raise self.retry(exc=e, countdown=300)  # Retry after 5 minutes


@shared_task(name='analytics.predict_revenue')
def predict_revenue_task(horizon_days: int = 30):
    """
    Predict daily revenue for the next N days
    Stores predictions in ForecastPoint model
    
    Args:
        horizon_days: Number of days to predict
    """
    from analytics.utils.forecasting import forecast_daily_revenue
    from analytics.models import ForecastPoint
    
    logger.info(f"Starting revenue prediction for {horizon_days} days")
    
    try:
        # Generate forecast
        forecast = forecast_daily_revenue(horizon_days=horizon_days)
        
        if not forecast:
            logger.warning("Revenue forecast returned None (insufficient data)")
            return {
                'success': False,
                'error': 'Insufficient historical data',
                'points_saved': 0
            }
        
        # Clear old forecasts for this series
        ForecastPoint.objects.filter(series_key='daily_revenue').delete()
        
        # Save forecast points
        points_created = 0
        for i, (date, yhat, ylow, yhigh) in enumerate(zip(
            forecast.dates, forecast.yhat, forecast.yhat_lower, forecast.yhat_upper
        )):
            ForecastPoint.objects.create(
                series_key='daily_revenue',
                date=date,
                yhat=yhat,
                yhat_lower=ylow,
                yhat_upper=yhigh
            )
            points_created += 1
        
        logger.info(f"Revenue prediction completed: {points_created} points saved")
        
        return {
            'success': True,
            'series': 'daily_revenue',
            'points_saved': points_created,
            'horizon_days': horizon_days,
            'date_range': f"{forecast.dates[0]} to {forecast.dates[-1]}"
        }
        
    except Exception as e:
        logger.error(f"Revenue prediction failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'points_saved': 0
        }


@shared_task(name='analytics.predict_leads')
def predict_leads_task(horizon_days: int = 30):
    """
    Predict new leads count for the next N days
    
    Args:
        horizon_days: Number of days to predict
    """
    from analytics.utils.forecasting import forecast_new_leads
    from analytics.models import ForecastPoint
    
    logger.info(f"Starting leads prediction for {horizon_days} days")
    
    try:
        forecast = forecast_new_leads(horizon_days=horizon_days)
        
        if not forecast:
            logger.warning("Leads forecast returned None (insufficient data)")
            return {
                'success': False,
                'error': 'Insufficient historical data',
                'points_saved': 0
            }
        
        # Clear old forecasts
        ForecastPoint.objects.filter(series_key='new_leads').delete()
        
        # Save forecast points
        points_created = 0
        for date, yhat, ylow, yhigh in zip(
            forecast.dates, forecast.yhat, forecast.yhat_lower, forecast.yhat_upper
        ):
            ForecastPoint.objects.create(
                series_key='new_leads',
                date=date,
                yhat=yhat,
                yhat_lower=ylow,
                yhat_upper=yhigh
            )
            points_created += 1
        
        logger.info(f"Leads prediction completed: {points_created} points saved")
        
        return {
            'success': True,
            'series': 'new_leads',
            'points_saved': points_created,
            'horizon_days': horizon_days
        }
        
    except Exception as e:
        logger.error(f"Leads prediction failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'points_saved': 0
        }


@shared_task(name='analytics.predict_clients')
def predict_clients_task(horizon_days: int = 30):
    """
    Predict new clients/companies count for the next N days
    
    Args:
        horizon_days: Number of days to predict
    """
    from analytics.utils.forecasting import forecast_new_clients_with_reach
    from analytics.models import ForecastPoint
    
    logger.info(f"Starting clients prediction for {horizon_days} days")
    
    try:
        forecast = forecast_new_clients_with_reach(horizon_days=horizon_days)
        
        if not forecast:
            logger.warning("Clients forecast returned None (insufficient data)")
            return {
                'success': False,
                'error': 'Insufficient historical data',
                'points_saved': 0
            }
        
        # Clear old forecasts
        ForecastPoint.objects.filter(series_key='new_clients').delete()
        
        # Save forecast points
        points_created = 0
        for date, yhat, ylow, yhigh in zip(
            forecast.dates, forecast.yhat, forecast.yhat_lower, forecast.yhat_upper
        ):
            ForecastPoint.objects.create(
                series_key='new_clients',
                date=date,
                yhat=yhat,
                yhat_lower=ylow,
                yhat_upper=yhigh
            )
            points_created += 1
        
        logger.info(f"Clients prediction completed: {points_created} points saved")
        
        return {
            'success': True,
            'series': 'new_clients',
            'points_saved': points_created,
            'horizon_days': horizon_days
        }
        
    except Exception as e:
        logger.error(f"Clients prediction failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'points_saved': 0
        }


@shared_task(name='analytics.predict_next_actions')
def predict_next_actions_task(limit_per_stage: int = 5):
    """
    Predict next best actions for active deals
    Uses stage transition probabilities
    
    Args:
        limit_per_stage: Max suggestions per stage
    """
    from analytics.utils.funnel_forecasting import suggest_next_actions
    from analytics.models import NextActionForecast
    
    logger.info(f"Starting next actions prediction (limit={limit_per_stage})")
    
    try:
        suggestions = suggest_next_actions(limit_per_stage=limit_per_stage)
        
        # Clear old predictions
        NextActionForecast.objects.all().delete()
        
        # Save new predictions
        forecasts_created = 0
        for suggestion in suggestions:
            NextActionForecast.objects.create(
                deal_id=suggestion.deal_id,
                suggested_action=suggestion.suggested_action,
                probability=suggestion.probability
            )
            forecasts_created += 1
        
        logger.info(f"Next actions prediction completed: {forecasts_created} forecasts saved")
        
        return {
            'success': True,
            'forecasts_saved': forecasts_created,
            'limit_per_stage': limit_per_stage
        }
        
    except Exception as e:
        logger.error(f"Next actions prediction failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'forecasts_saved': 0
        }


@shared_task(name='analytics.predict_client_actions')
def predict_client_actions_task(limit: int = 200):
    """
    Predict next best actions for clients/companies
    Based on active deals and historical patterns
    
    Args:
        limit: Max number of clients to predict
    """
    from analytics.utils.funnel_forecasting import suggest_next_actions_for_clients
    from analytics.models import ClientNextActionForecast
    
    logger.info(f"Starting client actions prediction (limit={limit})")
    
    try:
        suggestions = suggest_next_actions_for_clients(limit=limit)
        
        # Clear old predictions
        ClientNextActionForecast.objects.all().delete()
        
        # Save new predictions
        forecasts_created = 0
        for suggestion in suggestions:
            ClientNextActionForecast.objects.create(
                company_id=suggestion.company_id,
                suggested_action=suggestion.suggested_action,
                probability=suggestion.probability
            )
            forecasts_created += 1
        
        logger.info(f"Client actions prediction completed: {forecasts_created} forecasts saved")
        
        return {
            'success': True,
            'forecasts_saved': forecasts_created,
            'limit': limit
        }
        
    except Exception as e:
        logger.error(f"Client actions prediction failed: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'forecasts_saved': 0
        }


@shared_task(name='analytics.predict_all')
def predict_all_task(horizon_days: int = 30):
    """
    Run all prediction tasks in sequence
    
    Args:
        horizon_days: Forecast horizon for time-series predictions
    """
    logger.info("Starting comprehensive prediction run")
    
    results = {}
    
    # Revenue prediction
    try:
        results['revenue'] = predict_revenue_task(horizon_days)
    except Exception as e:
        logger.error(f"Revenue prediction failed: {str(e)}")
        results['revenue'] = {'success': False, 'error': str(e)}
    
    # Leads prediction
    try:
        results['leads'] = predict_leads_task(horizon_days)
    except Exception as e:
        logger.error(f"Leads prediction failed: {str(e)}")
        results['leads'] = {'success': False, 'error': str(e)}
    
    # Clients prediction
    try:
        results['clients'] = predict_clients_task(horizon_days)
    except Exception as e:
        logger.error(f"Clients prediction failed: {str(e)}")
        results['clients'] = {'success': False, 'error': str(e)}
    
    # Next actions for deals
    try:
        results['next_actions'] = predict_next_actions_task()
    except Exception as e:
        logger.error(f"Next actions prediction failed: {str(e)}")
        results['next_actions'] = {'success': False, 'error': str(e)}
    
    # Next actions for clients
    try:
        results['client_actions'] = predict_client_actions_task()
    except Exception as e:
        logger.error(f"Client actions prediction failed: {str(e)}")
        results['client_actions'] = {'success': False, 'error': str(e)}
    
    # Calculate summary
    total_success = sum(1 for r in results.values() if r.get('success'))
    total_tasks = len(results)
    
    logger.info(f"Comprehensive prediction completed: {total_success}/{total_tasks} tasks successful")
    
    return {
        'success': total_success == total_tasks,
        'completed_at': timezone.now().isoformat(),
        'results': results,
        'summary': {
            'successful': total_success,
            'failed': total_tasks - total_success,
            'total': total_tasks
        }
    }


@shared_task(name='analytics.cleanup_old_forecasts')
def cleanup_old_forecasts_task(days_to_keep: int = 90):
    """
    Clean up forecast predictions older than N days
    
    Args:
        days_to_keep: Keep forecasts from last N days
    """
    from analytics.models import ForecastPoint, NextActionForecast, ClientNextActionForecast
    
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    logger.info(f"Cleaning up forecasts older than {cutoff_date.date()}")
    
    try:
        # Clean forecast points
        fp_deleted = ForecastPoint.objects.filter(created_at__lt=cutoff_date).delete()[0]
        
        # Clean action forecasts
        naf_deleted = NextActionForecast.objects.filter(created_at__lt=cutoff_date).delete()[0]
        
        # Clean client action forecasts
        caf_deleted = ClientNextActionForecast.objects.filter(created_at__lt=cutoff_date).delete()[0]
        
        total_deleted = fp_deleted + naf_deleted + caf_deleted
        
        logger.info(f"Cleanup completed: {total_deleted} records deleted")
        
        return {
            'success': True,
            'deleted': {
                'forecast_points': fp_deleted,
                'next_actions': naf_deleted,
                'client_actions': caf_deleted,
                'total': total_deleted
            },
            'cutoff_date': cutoff_date.date().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Forecast cleanup failed: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
