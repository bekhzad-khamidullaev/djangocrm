from __future__ import annotations
from datetime import time


def is_quiet_hours(now_local: time, start: time | None, end: time | None) -> bool:
    if not (start and end):
        return False
    if start < end:
        return start <= now_local <= end
    # crosses midnight
    return now_local >= start or now_local <= end
