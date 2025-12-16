import base64
import json
import logging
import time
from typing import Optional
import requests
from smtplib import SMTP, SMTPException
from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend

logger = logging.getLogger(__name__)


class OAuth2EmailBackend(EmailBackend):
    """
    SMTP Email backend with OAuth2 support, timeouts, and retry logic.
    """
    def __init__(self, host=None, port=None, username=None, password=None,
                 use_tls=None, fail_silently=False, use_ssl=None, timeout=None,
                 ssl_keyfile=None, ssl_certfile=None, refresh_token=None,
                 **kwargs):
        super().__init__(host=host, port=port, username=username, password=password,
                         use_tls=use_tls, fail_silently=fail_silently, use_ssl=use_ssl,
                         timeout=timeout or 30, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile,
                         **kwargs)
        self.refresh_token = refresh_token
        self._max_retries = getattr(settings, 'EMAIL_OAUTH2_MAX_RETRIES', 3)
        self._retry_delay = getattr(settings, 'EMAIL_OAUTH2_RETRY_DELAY', 2)
        
    def get_access_token(self) -> str:
        """
        Get OAuth2 access token with retries and proper error handling.
        """
        if not hasattr(settings, 'CLIENT_ID') or not hasattr(settings, 'CLIENT_SECRET'):
            raise ValueError('CLIENT_ID and CLIENT_SECRET must be configured in settings')
        
        if not hasattr(settings, 'OAUTH2_DATA') or self.host not in settings.OAUTH2_DATA:
            raise ValueError(f'OAUTH2_DATA for host {self.host} not configured')
        
        oauth_data = settings.OAUTH2_DATA[self.host]
        request_url = f"{oauth_data['accounts_base_url']}/{oauth_data['token_command']}"
        
        # OAuth2 token requests should use form data (application/x-www-form-urlencoded) or JSON body
        payload = {
            'client_id': settings.CLIENT_ID,
            'client_secret': settings.CLIENT_SECRET,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token'
        }
        
        for attempt in range(self._max_retries):
            try:
                response = requests.post(
                    request_url,
                    data=payload,  # Use data for form-encoded; some providers accept json=payload
                    timeout=10,
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}
                )
                response.raise_for_status()
                
                result = response.json()
                if result.get('error'):
                    error_msg = f"OAuth2 error: {result.get('error')}, {result.get('error_description', '')}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                
                access_token = result.get('access_token')
                if not access_token:
                    raise ValueError('No access_token in OAuth2 response')
                
                return access_token
                
            except requests.exceptions.Timeout as e:
                logger.warning(f'OAuth2 token request timeout (attempt {attempt + 1}/{self._max_retries}): {e}')
                if attempt < self._max_retries - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
                else:
                    raise RuntimeError(f'OAuth2 token request timed out after {self._max_retries} attempts') from e
            
            except requests.exceptions.RequestException as e:
                logger.error(f'OAuth2 token request failed (attempt {attempt + 1}/{self._max_retries}): {e}')
                if attempt < self._max_retries - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
                else:
                    raise RuntimeError(f'OAuth2 token request failed after {self._max_retries} attempts: {e}') from e
            
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f'OAuth2 response parsing error: {e}')
                raise RuntimeError(f'Invalid OAuth2 response: {e}') from e
    
    def get_auth_string(self):
        access_token = self.get_access_token()
        auth_string = f"user={self.username}\1auth=Bearer {access_token}\1\1"
        auth_string_bytes = auth_string.encode("utf-8")
        auth_string_b64encoded = base64.b64encode(auth_string_bytes)
        auth_string_encoded = auth_string_b64encoded.decode("utf-8")
        return auth_string_encoded             

    def open(self):
        """
        Ensure an open connection to the email server with retry logic.
        Return whether or not a new connection was required (True or False)
        or None if an exception passed silently.
        """
        if self.connection:
            # Nothing to do if the connection is already open.
            return False

        connection_params = {}
        if self.timeout is not None:
            connection_params['timeout'] = self.timeout

        last_exception = None
        for attempt in range(self._max_retries):
            try:
                self.connection = SMTP(self.host, self.port, **connection_params)
                
                # STARTTLS for secure connection
                if self.use_tls:
                    self.connection.starttls()
                
                # OAuth2 authentication
                auth_string = self.get_auth_string()
                response = self.connection.docmd('AUTH', 'XOAUTH2 ' + auth_string)
                
                # Check auth response (235 is success)
                if response[0] != 235:
                    raise SMTPException(f"SMTP AUTH failed with response: {response}")
                
                logger.info(f'SMTP connection to {self.host}:{self.port} established successfully')
                return True
                
            except (OSError, SMTPException, RuntimeError) as e:
                last_exception = e
                logger.warning(f'SMTP connection attempt {attempt + 1}/{self._max_retries} failed: {e}')
                
                # Close any partial connection
                if self.connection:
                    try:
                        self.connection.quit()
                    except Exception:
                        pass
                    self.connection = None
                
                # Retry with exponential backoff
                if attempt < self._max_retries - 1:
                    time.sleep(self._retry_delay * (attempt + 1))
                else:
                    logger.error(f'SMTP connection failed after {self._max_retries} attempts: {last_exception}')
                    if not self.fail_silently:
                        raise RuntimeError(f'Failed to connect to SMTP server after {self._max_retries} attempts') from last_exception
                    return None
        
        return None
