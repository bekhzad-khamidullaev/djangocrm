"""
Centralized webhook signature validation and security utilities.
"""
import hmac
import secrets
from hashlib import sha1, sha256
from base64 import b64decode
from typing import Optional, Tuple
from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str:
    """Extract client IP considering reverse proxy headers."""
    for header in ('HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP'):
        value = request.META.get(header)
        if value:
            return value.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def validate_zadarma_signature(
    request: HttpRequest,
    data: str,
    secret: str,
    allowed_ips: list[str] = None
) -> Tuple[bool, str]:
    """
    Validate Zadarma webhook signature and IP.
    
    Args:
        request: Django request object
        data: Concatenated string of fields to sign (e.g., internal+phone+call_start)
        secret: Zadarma secret key
        allowed_ips: List of allowed IPs (None or empty = allow all)
    
    Returns:
        (is_valid, error_message)
    """
    if not data or not secret:
        return False, "Missing data or secret"
    
    # IP validation
    if allowed_ips:
        client_ip = get_client_ip(request)
        if client_ip not in allowed_ips:
            return False, f"IP {client_ip} not allowed"
    
    # Signature validation
    signature = request.headers.get('Signature')
    if not signature:
        return False, "Missing signature header"
    
    try:
        # Zadarma: base64-encoded HMAC-SHA1 digest
        expected_digest = hmac.new(
            secret.encode('utf-8'),
            data.encode('utf-8'),
            sha1
        ).digest()
        provided = b64decode(signature)
        
        if not secrets.compare_digest(provided, expected_digest):
            return False, "Invalid signature"
        
        return True, ""
    except Exception as e:
        return False, f"Signature validation error: {e}"


def validate_onlinepbx_signature(
    request: HttpRequest,
    token: Optional[str] = None,
    allowed_ips: list[str] = None
) -> Tuple[bool, str]:
    """
    Validate OnlinePBX webhook token and IP.
    
    Args:
        request: Django request object
        token: Expected webhook token (None = no token check)
        allowed_ips: List of allowed IPs (None or empty = allow all)
    
    Returns:
        (is_valid, error_message)
    """
    # IP validation
    if allowed_ips:
        client_ip = get_client_ip(request)
        if client_ip not in allowed_ips:
            return False, f"IP {client_ip} not allowed"
    
    # Token validation
    if token:
        received = request.headers.get('X-OnlinePBX-Token') or request.headers.get('X-Obx-Token')
        if not received or received != token:
            return False, "Invalid or missing token"
    
    return True, ""


def validate_generic_hmac(
    request: HttpRequest,
    payload: bytes,
    secret: str,
    header_name: str = 'X-Hub-Signature-256',
    algorithm: str = 'sha256',
    prefix: str = 'sha256='
) -> Tuple[bool, str]:
    """
    Generic HMAC signature validation (e.g., GitHub, GitLab style).
    
    Args:
        request: Django request object
        payload: Raw request body bytes
        secret: Secret key for HMAC
        header_name: Header containing the signature
        algorithm: Hash algorithm ('sha1', 'sha256', etc.)
        prefix: Signature prefix (e.g., 'sha256=')
    
    Returns:
        (is_valid, error_message)
    """
    signature_header = request.headers.get(header_name)
    if not signature_header:
        return False, f"Missing {header_name} header"
    
    if not signature_header.startswith(prefix):
        return False, f"Invalid signature format (expected {prefix})"
    
    provided_sig = signature_header[len(prefix):]
    
    hash_func = {'sha1': sha1, 'sha256': sha256}.get(algorithm)
    if not hash_func:
        return False, f"Unsupported algorithm: {algorithm}"
    
    try:
        expected = hmac.new(
            secret.encode('utf-8'),
            payload,
            hash_func
        ).hexdigest()
        
        if not secrets.compare_digest(provided_sig, expected):
            return False, "Invalid signature"
        
        return True, ""
    except Exception as e:
        return False, f"Signature validation error: {e}"
