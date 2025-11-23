from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


@dataclass
class RenderResult:
    subject: str
    body: str


URL_RE = re.compile(r"(?P<url>https?://[\w\-\._~:/\?#\[\]@!$&'()*+,;=%]+)")


def merge_utm(query_items: list[tuple[str, str]], utm: Dict[str, str]) -> list[tuple[str, str]]:
    if not utm:
        return query_items
    # keep existing params, add/override utm_*
    q = dict(query_items)
    for k, v in utm.items():
        if not k.startswith('utm_'):
            key = f'utm_{k}'
        else:
            key = k
        if v is not None:
            q[key] = str(v)
    # preserve order: utm_* last
    non_utm = [(k, v) for k, v in q.items() if not k.startswith('utm_')]
    utm_items = [(k, v) for k, v in q.items() if k.startswith('utm_')]
    return non_utm + utm_items


def add_utm_to_text(text: str, utm: Optional[Dict[str, str]]) -> str:
    if not utm:
        return text

    def repl(m: re.Match) -> str:
        url = m.group('url')
        try:
            parsed = urlparse(url)
            qs = parse_qsl(parsed.query, keep_blank_values=True)
            merged = merge_utm(qs, utm)
            new_qs = urlencode(merged)
            new_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_qs, parsed.fragment))
            return new_url
        except Exception:
            return url

    return URL_RE.sub(repl, text)


def render_template(template_body: str, variables: Optional[Dict[str, str]] = None, utm: Optional[Dict[str, str]] = None) -> RenderResult:
    body = template_body or ''
    for k, v in (variables or {}).items():
        body = body.replace('{' + k + '}', str(v))
    # Append UTM parameters to all links in body
    body = add_utm_to_text(body, utm)
    return RenderResult(subject='', body=body)
