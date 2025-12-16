import jwt
from datetime import datetime, timedelta
from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth import get_user_model
from django.http import JsonResponse
# from rest_framework_simplejwt.tokens import RefreshToken
# from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.conf import settings

from .models import AuthenticationLog


User = get_user_model()


class JWTRefreshMiddleware(MiddlewareMixin):
    """
    Middleware to automatically refresh JWT access tokens when they are close to expiration.
    
    Checks if access token will expire within 5 minutes and automatically refreshes it
    using the refresh token from cookies or X-Refresh-Token header.
    """
    
    def process_request(self, request):
        # Skip for non-API endpoints
        if not request.path.startswith('/api/'):
            return None
        
        # Skip for auth endpoints themselves
        if request.path in ['/api/token/', '/api/token/refresh/', '/api/token/verify/']:
            return None
        
        # Get authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header.startswith('Bearer '):
            return None
        
        access_token = auth_header.split(' ')[1]
        
        try:
            # Decode token without verification to check expiration
            decoded = jwt.decode(
                access_token,
                settings.SECRET_KEY,
                algorithms=['HS256'],
                options={'verify_exp': False}
            )
            
            exp = decoded.get('exp')
            if not exp:
                return None
            
            # Check if token expires in less than 5 minutes
            exp_datetime = datetime.fromtimestamp(exp)
            time_until_exp = exp_datetime - datetime.now()
            
            if time_until_exp < timedelta(minutes=5):
                # Token is about to expire, try to refresh
                refresh_token = self._get_refresh_token(request)
                
                # Do not auto-refresh in middleware; only signal near expiry
                if time_until_exp < timedelta(minutes=5):
                    request._token_near_expiry = True
        
        except jwt.DecodeError:
            pass  # Invalid token, let authentication backend handle it
        except Exception:
            pass  # Any other error, continue normally
        
        return None
    
    def process_response(self, request, response):
        """Add refreshed tokens to response headers"""
        # If token is near expiry, hint client to refresh via standard endpoint
        if getattr(request, '_token_near_expiry', False):
            response['X-Token-Near-Expiry'] = 'true'
        return response
    
    def _get_refresh_token(self, request):
        """Get refresh token from cookie or header"""
        # Try to get from cookie first
        refresh_token = request.COOKIES.get('refresh_token')
        
        # If not in cookie, try custom header
        if not refresh_token:
            refresh_token = request.META.get('HTTP_X_REFRESH_TOKEN')
        
        return refresh_token
    
    # Auto refresh disabled: use SimpleJWT TokenRefreshView instead
        """Refresh access token using refresh token"""
        try:
            refresh = RefreshToken(refresh_token_str)
            new_access = str(refresh.access_token)
            
            result = {'access': new_access}
            
            # If rotation is enabled, we get a new refresh token too
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
                refresh.set_jti()
                refresh.set_exp()
                result['refresh'] = str(refresh)
            
            return result
        
        except (TokenError, InvalidToken):
            return None


class AuthenticationLoggingMiddleware(MiddlewareMixin):
    """
    Middleware to log all authentication attempts for monitoring JWT vs legacy token usage.
    """
    
    def process_request(self, request):
        # Skip non-API endpoints
        if not request.path.startswith('/api/'):
            return None
        
        # Skip static files and docs
        if any(request.path.startswith(p) for p in ['/api/schema/', '/api/docs/', '/api/redoc/']):
            return None
        
        # Store request info for later logging
        request._auth_log_data = {
            'endpoint': request.path,
            'method': request.method,
            'ip_address': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', '')[:500],
        }
        
        return None
    
    def process_response(self, request, response):
        """Log authentication after response is ready"""
        if not hasattr(request, '_auth_log_data'):
            return response
        
        # Only log if user was authenticated (or attempted to authenticate)
        if hasattr(request, 'user') and request.user.is_authenticated:
            auth_type = self._detect_auth_type(request)
            
            # Log successful authentication
            self._log_authentication(
                user=request.user,
                username=request.user.username,
                auth_type=auth_type,
                success=True,
                **request._auth_log_data
            )
        elif response.status_code == 401:
            # Log failed authentication
            auth_type = self._detect_auth_type(request)
            username = self._extract_username(request)
            
            self._log_authentication(
                user=None,
                username=username or 'anonymous',
                auth_type=auth_type,
                success=False,
                **request._auth_log_data
            )
        
        return response
    
    def _detect_auth_type(self, request):
        """Detect which authentication method was used"""
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if auth_header.startswith('Bearer '):
            return 'jwt'
        elif auth_header.startswith('Token '):
            return 'legacy'
        elif request.session.get('_auth_user_id'):
            return 'session'
        
        return 'jwt'  # Default assumption for API
    
    def _get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def _extract_username(self, request):
        """Try to extract username from failed auth attempt"""
        # For token endpoints, try to get from POST data
        if request.path in ['/api/token/', '/api/auth/token/']:
            try:
                return request.POST.get('username') or request.data.get('username')
            except:
                pass
        
        return None
    
    def _log_authentication(self, user, username, auth_type, success, endpoint, method, ip_address, user_agent):
        """Create authentication log entry"""
        try:
            AuthenticationLog.objects.create(
                user=user,
                username=username,
                auth_type=auth_type,
                endpoint=endpoint,
                method=method,
                success=success,
                ip_address=ip_address,
                user_agent=user_agent
            )
        except Exception:
            # Don't break the request if logging fails
            pass
