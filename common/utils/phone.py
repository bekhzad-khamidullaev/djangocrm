import re
from typing import Optional

E164_RE = re.compile(r"^\+?[1-9]\d{6,14}$")


def to_e164(raw: Optional[str]) -> str:
    """Normalize phone to E.164-like string (simple heuristic).
    Keeps leading +, strips non-digits. Returns '' if not valid length.
    """
    if not raw:
        return ''
    s = str(raw).strip()
    if s.startswith('+'):
        s = '+' + ''.join(ch for ch in s[1:] if ch.isdigit())
    else:
        s = ''.join(ch for ch in s if ch.isdigit())
        if s:
            s = '+' + s
    # basic length check
    if 7 <= len(s.lstrip('+')) <= 15:
        return s
    return ''
