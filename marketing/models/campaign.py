from __future__ import annotations
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Channel(models.TextChoices):
    SMS = 'sms', 'SMS'
    TELEGRAM = 'tg', 'Telegram'
    INSTAGRAM = 'ig', 'Instagram'
    CALL = 'call', 'Phone Call'
    EMAIL = 'email', 'Email'


class Campaign(models.Model):
    name = models.CharField(max_length=200)
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.SMS)
    segment = models.ForeignKey('marketing.Segment', null=True, blank=True, on_delete=models.SET_NULL)
    template = models.ForeignKey('marketing.MessageTemplate', null=True, blank=True, on_delete=models.SET_NULL)
    start_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name


class CampaignRun(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='runs')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    size = models.IntegerField(default=0)
    sent = models.IntegerField(default=0)
    delivered = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    replied = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f"Run #{self.id} of {self.campaign}"
