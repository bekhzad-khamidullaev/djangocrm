from __future__ import annotations
from django.db import models
from django.utils.translation import gettext_lazy as _


class MessageTemplate(models.Model):
    name = models.CharField(max_length=200)
    channel = models.CharField(max_length=16, choices=[('sms','SMS'),('tg','Telegram'),('ig','Instagram'),('email','Email')], default='sms')
    locale = models.CharField(max_length=10, blank=True, default='')
    subject = models.CharField(max_length=200, blank=True, default='')
    body = models.TextField()
    variables = models.JSONField(default=list, blank=True, help_text=_('List of variables used in template'))
    version = models.IntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.name} [{self.channel}]"
