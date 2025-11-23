from __future__ import annotations
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class Preferences(models.Model):
    target_ct = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target_id = models.PositiveIntegerField()
    target = GenericForeignKey('target_ct', 'target_id')

    allow_sms = models.BooleanField(default=True)
    allow_tg = models.BooleanField(default=True)
    allow_ig = models.BooleanField(default=True)
    allow_email = models.BooleanField(default=True)
    quiet_hours_from = models.TimeField(null=True, blank=True)
    quiet_hours_to = models.TimeField(null=True, blank=True)
    daily_limit_sms = models.IntegerField(default=5)
    weekly_limit_sms = models.IntegerField(default=15)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Prefs for {self.target}"
