from __future__ import annotations
from django.db import models


class Segment(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    rules = models.JSONField(default=dict, blank=True)
    size_cache = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name
