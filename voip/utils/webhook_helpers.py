"""
Webhook helpers for rate limiting and idempotency.
"""
from functools import wraps
from typing import Optional
from django.http import HttpResponse
from django.core.cache import cache
from django.db import IntegrityError


def check_webhook_idempotency(provider: str, event_id: str, event_type: str = '', payload: dict = None) -> bool:
    """
    Check if webhook event was already processed. Returns True if event is new (should process).
    Creates WebhookEvent record if new.
    
    Args:
        provider: Provider name ('zadarma', 'onlinepbx', 'asterisk')
        event_id: Unique event identifier (call_id, uuid)
        event_type: Event type (optional)
        payload: Raw payload dict (optional)
    
    Returns:
        True if event is new and should be processed, False if already processed
    """
    if not event_id:
        return True  # No ID, process anyway
    
    from voip.models import WebhookEvent
    
    try:
        WebhookEvent.objects.create(
            provider=provider.lower(),
            event_id=event_id,
            event_type=event_type,
            payload=payload or {}
        )
        return True  # New event
    except IntegrityError:
        return False  # Already processed


def rate_limit_webhook(provider: str, max_requests: int = 100, window_seconds: int = 60):
    """
    Decorator to rate limit webhook requests per provider.
    
    Args:
        provider: Provider identifier
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds
    
    Usage:
        @rate_limit_webhook('zadarma', max_requests=100, window_seconds=60)
        def post(self, request):
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract request from args (django view convention: self, request)
            request = args[1] if len(args) > 1 else kwargs.get('request')
            if not request:
                return func(*args, **kwargs)
            
            # Build cache key with provider and IP
            from voip.utils.webhook_validators import get_client_ip
            client_ip = get_client_ip(request)
            cache_key = f'webhook_ratelimit:{provider}:{client_ip}'
            
            # Get current count
            current = cache.get(cache_key, 0)
            
            if current >= max_requests:
                return HttpResponse('Rate limit exceeded', status=429)
            
            # Increment counter
            cache.set(cache_key, current + 1, window_seconds)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


def get_or_none(model_class, **kwargs):
    """Helper to get model instance or None."""
    try:
        return model_class.objects.get(**kwargs)
    except model_class.DoesNotExist:
        return None
    except model_class.MultipleObjectsReturned:
        return model_class.objects.filter(**kwargs).first()
