from django.db import models
from django.utils.translation import gettext_lazy as _

from common.models import Base1
from crm.models import ClosingReason
from crm.models import Deal
from crm.models import LeadSource
from crm.models import Payment
from crm.models import Request


class IncomeStatSnapshot(Base1):
    
    class Meta:
        verbose_name = _('IncomeStat Snapshot')
        verbose_name_plural = _('IncomeStat Snapshots')
            
    webpage = models.TextField(
        blank=True, default='',
    )        
    update_date = None


class OutputStat(Payment):
    
    class Meta:
        proxy = True
        verbose_name = _('Sales Report')
        verbose_name_plural = _('Sales Report')
        

class RequestStat(Request):
    
    class Meta:
        proxy = True
        verbose_name = _('Request Summary')
        verbose_name_plural = _('Requests Summary')
        
        
class LeadSourceStat(LeadSource):
    
    class Meta:
        proxy = True
        verbose_name = _('Lead source Summary')
        verbose_name_plural = _('Lead source Summary')
        
        
class ClosingReasonStat(ClosingReason):
    
    class Meta:
        proxy = True
        verbose_name = _('Closing reason Summary')
        verbose_name_plural = _('Closing reason Summary')
        
        
class DealStat(Deal):
    
    class Meta:
        proxy = True
        verbose_name = _('Deal Summary')
        verbose_name_plural = _('Deal Summary')
        
         
class IncomeStat(Deal):
    
    class Meta:
        proxy = True
        verbose_name = _('Income Summary')
        verbose_name_plural = _('Income Summary')
        
        
class SalesFunnel(Deal):
    
    class Meta:
        proxy = True
        verbose_name = _('Sales funnel')
        verbose_name_plural = _('Sales funnel')
        
class ForecastPoint(models.Model):
    series_key = models.CharField(max_length=64, db_index=True)
    date = models.DateField(db_index=True)
    yhat = models.FloatField()
    yhat_lower = models.FloatField(null=True, blank=True)
    yhat_upper = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Forecast point')
        verbose_name_plural = _('Forecast points')
        unique_together = (('series_key', 'date'),)


class NextActionForecast(models.Model):
    deal_id = models.BigIntegerField(db_index=True)
    suggested_action = models.CharField(max_length=64)
    probability = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Next action forecast')
        verbose_name_plural = _('Next action forecasts')
        unique_together = (('deal_id', 'suggested_action'),)


class ClientNextActionForecast(models.Model):
    company_id = models.BigIntegerField(db_index=True)
    suggested_action = models.CharField(max_length=64)
    probability = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Client next action forecast')
        verbose_name_plural = _('Client next action forecasts')
        unique_together = (('company_id', 'suggested_action'),)


class ForecastsStat(Deal):
    class Meta:
        proxy = True
        verbose_name = _('Forecasts')
        verbose_name_plural = _('Forecasts')


class DailyRevenueStat(Deal):
    class Meta:
        proxy = True
        verbose_name = _('Daily Revenue Forecast')
        verbose_name_plural = _('Daily Revenue Forecast')
    class Meta:
        proxy = True
        verbose_name = _('Forecasts')
        verbose_name_plural = _('Forecasts')
        
class BIStat(Deal):
    class Meta:
        proxy = True
        verbose_name = _('BI Analytics')
        verbose_name_plural = _('BI Analytics')
        
class ConversionStat(Request):
    
    class Meta:
        proxy = True
        verbose_name = _('Conversion Summary')
        verbose_name_plural = _('Conversion Summary')
