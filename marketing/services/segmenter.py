from __future__ import annotations
from typing import Iterable
from django.contrib.contenttypes.models import ContentType
from crm.models import Contact, Lead, Company, Deal


def evaluate_segment(rules: dict) -> Iterable[tuple[ContentType, int]]:
    # Minimal MVP: support all objects segment (empty rules)
    # Later: build QuerySets by rules
    res = []
    for model in (Contact, Lead, Company, Deal):
        ct = ContentType.objects.get_for_model(model)
        qs = model.objects.all()
        res.extend((ct, obj.id) for obj in qs[:200])  # cap preview
    return res
