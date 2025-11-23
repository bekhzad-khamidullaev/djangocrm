from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from collections import defaultdict
from django.utils import timezone
from datetime import timedelta

from crm.models import Deal
from typing import Tuple

@dataclass
class ClientNextAction:
    company_id: int
    suggested_action: str
    probability: float


@dataclass
class NextAction:
    deal_id: int
    suggested_action: str
    probability: float


ACTION_ORDER = [
    'call', 'email', 'schedule_meeting', 'send_proposal', 'follow_up', 'close_deal'
]


def compute_stage_transition_probabilities(window_days: int = 90) -> Dict[str, Dict[str, float]]:
    """
    Compute naive per-stage next action probabilities using available fields.
    Since we do not have explicit event logs, we approximate based on:
    - deals with next_step text patterns
    - stages with success flags (close_deal)
    This is a heuristic placeholder that can be improved when event history is available.
    """
    now = timezone.now()
    start = now - timedelta(days=window_days)
    qs = Deal.objects.filter(creation_date__gte=start)

    stage_counts = defaultdict(int)
    action_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for d in qs.select_related('stage'):
        stage_name = d.stage.name if d.stage else 'Unknown'
        stage_counts[stage_name] += 1
        text = (d.next_step or '').lower()
        action = None
        if 'call' in text or 'звон' in text:
            action = 'call'
        elif 'mail' in text or 'пис' in text or 'email' in text:
            action = 'email'
        elif 'meet' in text or 'встреч' in text:
            action = 'schedule_meeting'
        elif 'propos' in text or 'коммер' in text:
            action = 'send_proposal'
        elif 'follow' in text or 'напом' in text:
            action = 'follow_up'
        elif d.stage and (getattr(d.stage, 'success_stage', False) or getattr(d.stage, 'conditional_success_stage', False)):
            action = 'close_deal'
        if not action:
            action = 'follow_up'
        action_counts[stage_name][action] += 1

    probs: Dict[str, Dict[str, float]] = {}
    for stage, counts in action_counts.items():
        total = max(1, stage_counts[stage])
        probs[stage] = {a: round(c / total, 4) for a, c in counts.items()}
        # Normalize and order
        s = sum(probs[stage].values())
        if s > 0:
            for a in list(probs[stage].keys()):
                probs[stage][a] = round(probs[stage][a] / s, 4)
    return probs


def suggest_next_actions(limit_per_stage: int = 5) -> List[NextAction]:
    """
    Suggest next actions for active deals based on stage probabilities and each deal's next_step text.
    """
    probs = compute_stage_transition_probabilities()
    suggestions: List[NextAction] = []

    # Sample a few per stage
    per_stage: Dict[str, int] = defaultdict(int)
    for d in Deal.objects.select_related('stage').order_by('-creation_date')[:500]:
        stage_name = d.stage.name if d.stage else 'Unknown'
        pmap = probs.get(stage_name) or {}
        # choose highest probability action
        if pmap:
            action = sorted(pmap.items(), key=lambda x: x[1], reverse=True)[0]
            suggestions.append(NextAction(deal_id=d.id, suggested_action=action[0], probability=float(action[1])))
            per_stage[stage_name] += 1
            if per_stage[stage_name] >= limit_per_stage:
                continue
        else:
            suggestions.append(NextAction(deal_id=d.id, suggested_action='follow_up', probability=0.3))
    return suggestions


def suggest_next_actions_for_clients(limit: int = 200) -> List[ClientNextAction]:
    """
    Predict next actions per client (company) by aggregating deals and using stage probabilities + next_step hints.
    Returns up to 'limit' clients with the most recent activity.
    """
    probs = compute_stage_transition_probabilities()
    out: List[ClientNextAction] = []

    qs = Deal.objects.select_related('stage','company').exclude(company__isnull=True).order_by('-creation_date')
    seen = set()
    for d in qs:
        cid = d.company_id
        if not cid or cid in seen:
            continue
        seen.add(cid)
        stage_name = d.stage.name if d.stage else 'Unknown'
        pmap = probs.get(stage_name) or {}
        if pmap:
            action = sorted(pmap.items(), key=lambda x: x[1], reverse=True)[0]
            out.append(ClientNextAction(company_id=cid, suggested_action=action[0], probability=float(action[1])))
        else:
            # Fallback to next_step text
            text = (d.next_step or '').lower()
            if 'call' in text or 'звон' in text:
                out.append(ClientNextAction(company_id=cid, suggested_action='call', probability=0.4))
            elif 'mail' in text or 'пис' in text or 'email' in text:
                out.append(ClientNextAction(company_id=cid, suggested_action='email', probability=0.35))
            elif 'meet' in text or 'встреч' in text:
                out.append(ClientNextAction(company_id=cid, suggested_action='schedule_meeting', probability=0.35))
            elif 'propos' in text or 'коммер' in text:
                out.append(ClientNextAction(company_id=cid, suggested_action='send_proposal', probability=0.35))
            else:
                out.append(ClientNextAction(company_id=cid, suggested_action='follow_up', probability=0.3))
        if len(out) >= limit:
            break
    return out

