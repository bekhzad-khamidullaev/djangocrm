from __future__ import annotations
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class DeliveryTask(models.Model):
    campaign_run = models.ForeignKey('marketing.CampaignRun', on_delete=models.CASCADE, related_name='tasks')
    target_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_ct', 'target_id')
    status = models.CharField(max_length=16, default='queued')  # queued, sent, delivered, failed
    detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class DeliveryLog(models.Model):
    task = models.ForeignKey(DeliveryTask, on_delete=models.CASCADE, related_name='logs')
    status = models.CharField(max_length=16)
    detail = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
