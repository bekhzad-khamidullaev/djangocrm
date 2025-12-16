import os
import threading
import logging
from collections import defaultdict
from datetime import datetime as dt
from datetime import timedelta
from random import random
from time import sleep
from typing import Optional
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import mail_admins
from django.core.cache import cache

from crm.settings import IMAP_CONNECTION_IDLE
from crm.settings import IMAP_NOOP_PERIOD
from crm.utils.crm_imap import CrmIMAP
from massmail.models import EmailAccount

logger = logging.getLogger(__name__)

delta_period = timedelta(seconds=30)
idle_period = timedelta(days=IMAP_CONNECTION_IDLE)

# Error notification throttling settings
ERROR_NOTIFICATION_WINDOW = 3600  # seconds (1 hour)
MAX_ERRORS_PER_WINDOW = 3  # max emails per hour per error type


class CrmImapManager(threading.Thread):
    """Create and manage CrmIMAP objects."""

    def __init__(self, ea_queue): 
        threading.Thread.__init__(self)
        self.daemon = True
        self.boxes_storage = {}
        self.close = False
        self.ea_queue = ea_queue
        self.crmimap_storage = {}

    def get_crmimap(self, ea: EmailAccount, 
                    box: Optional[str] = None) -> Optional[CrmIMAP]:
        """
        Get or create CrmIMAP connection for email account.
        Returns None in testing or if connection fails.
        Callers must handle None gracefully.
        """
        if settings.TESTING:
            logger.debug(f'get_crmimap: skipping in test mode for {ea.email_host_user}')
            return None
        
        try:
            crmimap = self._get_or_create_crmimap(ea, box)
            if crmimap is None:
                logger.warning(f'get_crmimap: failed to get/create IMAP connection for {ea.email_host_user}')
            return crmimap
        except Exception as e:
            logger.error(f'get_crmimap: exception for {ea.email_host_user}: {e}', exc_info=True)
            self._throttled_error_notification('get_crmimap_exception', str(e))
            return None

    def run(self) -> None:
        if settings.REUSE_IMAP_CONNECTION:
            if not settings.TESTING:
                s = int(random() * IMAP_NOOP_PERIOD)
                sleep(s)
                self._keep_in_touch()
    
    def _create_crmimap(self, ea: EmailAccount) -> Optional[CrmIMAP]:
        """Create new CrmIMAP connection. Returns None on error."""
        try:
            crmimap = CrmIMAP(ea.email_host_user)
            if ea.email_host_user not in self.crmimap_storage:
                if settings.REUSE_IMAP_CONNECTION:
                    self.crmimap_storage[ea.email_host_user] = crmimap
                boxes = self.boxes_storage.get(ea.email_host_user)
                crmimap.get_in(boxes, ea)
                if crmimap.error:
                    logger.error(f'_create_crmimap: connection error for {ea.email_host_user}: {crmimap.error}')
                    return None
                if not boxes:
                    self.boxes_storage[ea.email_host_user] = crmimap.boxes
                logger.info(f'_create_crmimap: successfully created IMAP connection for {ea.email_host_user}')
            else:
                crmimap = self.crmimap_storage.get(ea.email_host_user)
                if not crmimap:
                    logger.error(f'_create_crmimap: stored crmimap is None for {ea.email_host_user}')
                    return None
            crmimap.last_request_time = dt.now()
            return crmimap
        except Exception as e:
            logger.error(f'_create_crmimap: exception for {ea.email_host_user}: {e}', exc_info=True)
            return None

    def _del_crmimap(self, crmimap: CrmIMAP) -> None:
        del self.crmimap_storage[crmimap.email_host_user]
        crmimap.close_and_logout()

    def _get_crmimap(self, ea: EmailAccount) -> Optional[CrmIMAP]:
        """Get existing CrmIMAP connection if valid, None otherwise."""
        crmimap = None
        if settings.REUSE_IMAP_CONNECTION:
            crmimap = self.crmimap_storage.get(ea.email_host_user)
            if crmimap:
                try:
                    crmimap.lock()
                    if not crmimap.error:
                        crmimap.last_request_time = dt.now()
                        result = crmimap.noop()
                        if result != 'OK' or crmimap.error:
                            logger.warning(f'_get_crmimap: noop check failed for {ea.email_host_user}, deleting')
                            self._del_crmimap(crmimap)
                            crmimap = None
                    else:
                        logger.warning(f'_get_crmimap: existing connection has error for {ea.email_host_user}, deleting')
                        self._del_crmimap(crmimap)
                        crmimap = None
                except Exception as e:
                    logger.error(f'_get_crmimap: exception checking connection for {ea.email_host_user}: {e}')
                    try:
                        self._del_crmimap(crmimap)
                    except Exception:
                        pass
                    crmimap = None
        return crmimap

    def _get_or_create_crmimap(self, ea: EmailAccount, 
                               box: Optional[str]) -> Optional[CrmIMAP]:
        crmimap = self._get_crmimap(ea) or self._create_crmimap(ea)
        if crmimap and not crmimap.error and box:
            crmimap.select_box(box)
        return crmimap

    def _keep_in_touch(self) -> None:
        while True:
            key_list = list(self.crmimap_storage.keys())
            for key in key_list:
                value = getattr(self.crmimap_storage.get(key, None), 'locked')
                if value is False:
                    self.crmimap_storage[key].locked = True
                    self._serve_crmimap(key)

            sleep(IMAP_NOOP_PERIOD)

    def _throttled_error_notification(self, error_type: str, error_message: str) -> None:
        """
        Send admin notification with throttling to prevent email storms.
        Uses cache to track notification counts per error type.
        """
        cache_key = f'imap_error_throttle:{error_type}'
        error_count = cache.get(cache_key, 0)
        
        if error_count < MAX_ERRORS_PER_WINDOW:
            # Send notification
            try:
                site = Site.objects.get_current()
                mail_admins(
                    f"IMAP Error: {error_type}",
                    f"""Error type: {error_type}
Error message: {error_message}
Time: {dt.now()}
Site: {site.domain}
Thread: {threading.current_thread()}
Process: {os.getpid()}

This is notification {error_count + 1}/{MAX_ERRORS_PER_WINDOW} for this error type in the last hour.
Further notifications for this error type will be suppressed until the window resets.
"""
                )
                logger.info(f'Sent throttled admin notification for {error_type} ({error_count + 1}/{MAX_ERRORS_PER_WINDOW})')
            except Exception as e:
                logger.error(f'Failed to send admin notification: {e}')
        else:
            logger.warning(f'Suppressed admin notification for {error_type} (limit {MAX_ERRORS_PER_WINDOW} reached)')
        
        # Increment counter
        cache.set(cache_key, error_count + 1, ERROR_NOTIFICATION_WINDOW)
    
    def _serve_crmimap(self, key) -> None:
        try:
            crmimap = self.crmimap_storage.get(key)
            if not crmimap:
                logger.warning(f'_serve_crmimap: crmimap not found for key {key}')
                return
            
            now = dt.now()
            request_time_delta = now - crmimap.last_request_time
            if crmimap.noop_time:
                noop_time_delta = now - crmimap.noop_time
            else:
                noop_time_delta = request_time_delta

            ea = crmimap.ea
            if noop_time_delta > delta_period and \
                    request_time_delta > delta_period:
                crmimap.noop_time = now
                result = crmimap.noop()
                if result != 'OK':
                    logger.warning(f'_serve_crmimap: noop failed for {key}, recreating connection')
                    self._del_crmimap(crmimap)
                    crmimap = self._create_crmimap(ea)
                    if not crmimap:
                        logger.error(f'_serve_crmimap: failed to recreate connection for {key}')

            if crmimap:
                crmimap.release()
                self.ea_queue.put(ea)
        except Exception as err:
            logger.error(f'_serve_crmimap exception for key {key}: {err}', exc_info=True)
            self._throttled_error_notification('serve_crmimap_exception', str(err))        
