# -*- coding: utf-8 -*-
"""
Utilities for Asterisk Real-time configuration management
"""

import logging
import secrets
import string
from typing import Dict, List, Optional, Any
from django.db import transaction
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()


def generate_secure_password(length: int = 16) -> str:
    """
    Generate cryptographically secure random password
    
    :param length: Password length
    :return: Random password
    """
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def auto_provision_endpoint(user, extension_number: str = None, 
                            password: str = None, context: str = 'from-internal',
                            transport: str = 'transport-udp') -> Dict[str, Any]:
    """
    Automatically provision a complete SIP endpoint for a user
    
    :param user: Django User instance
    :param extension_number: Extension number (auto-generated if None)
    :param password: SIP password (auto-generated if None)
    :param context: Dialplan context
    :param transport: Transport to use
    :return: Provisioning result with credentials
    """
    from voip.models import PsEndpoint, PsAuth, PsAor, InternalNumber, SipServer
    
    try:
        # Get or create default SIP server
        sip_server = SipServer.objects.filter(active=True).first()
        if not sip_server:
            logger.warning("No active SIP server found, skipping InternalNumber creation")
            sip_server = None
        
        # Generate extension number if not provided
        if not extension_number:
            if sip_server:
                extension_number = InternalNumber.generate_next_number(sip_server)
            else:
                # Fallback: use simple counter
                from voip.models import PsEndpoint
                existing = PsEndpoint.objects.using('asterisk').all().order_by('-id')
                if existing.exists():
                    try:
                        last_num = int(existing.first().id)
                        extension_number = str(last_num + 1)
                    except (ValueError, AttributeError):
                        extension_number = '1000'
                else:
                    extension_number = '1000'
        
        # Generate password if not provided
        if not password:
            password = generate_secure_password(16)
        
        # Prepare caller ID
        full_name = user.get_full_name() or user.username
        callerid = f'"{full_name}" <{extension_number}>'
        
        with transaction.atomic(using='asterisk'):
            # Create Auth
            auth = PsAuth.objects.using('asterisk').create(
                id=extension_number,
                auth_type='userpass',
                username=extension_number,
                password=password
            )
            
            # Create AOR
            aor = PsAor.objects.using('asterisk').create(
                id=extension_number,
                max_contacts=3,  # Allow multiple devices
                remove_existing='no',  # Keep existing contacts
                qualify_frequency=60,  # Check every 60 seconds
                default_expiration=3600
            )
            
            # Create Endpoint
            endpoint = PsEndpoint.objects.using('asterisk').create(
                id=extension_number,
                transport=transport,
                context=context,
                aors=extension_number,
                auth=extension_number,
                callerid=callerid,
                disallow='all',
                allow='ulaw,alaw,gsm,g722',
                direct_media='no',
                rtp_symmetric='yes',
                force_rport='yes',
                rewrite_contact='yes',
                dtmf_mode='rfc4733',
                device_state_busy_at=2,
                crm_user_id=user.id
            )
        
        # Create InternalNumber record if SIP server exists
        if sip_server:
            internal_number, created = InternalNumber.objects.get_or_create(
                server=sip_server,
                number=extension_number,
                defaults={
                    'user': user,
                    'password': password,
                    'display_name': full_name,
                    'active': True,
                    'auto_generated': True
                }
            )
            if not created:
                # Update existing
                internal_number.user = user
                internal_number.password = password
                internal_number.display_name = full_name
                internal_number.save()
        
        # Generate basic dialplan
        generate_dialplan_for_endpoint(extension_number, context)
        
        logger.info(f"Auto-provisioned endpoint {extension_number} for user {user.username}")
        
        return {
            'success': True,
            'endpoint_id': extension_number,
            'username': extension_number,
            'password': password,
            'callerid': callerid,
            'context': context,
            'user': user.username,
            'sip_uri': f'sip:{extension_number}@asterisk'
        }
        
    except Exception as e:
        logger.error(f"Error auto-provisioning endpoint for user {user.username}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e),
            'user': user.username
        }


def sync_internal_numbers():
    """
    Synchronize InternalNumber models with Asterisk Real-time endpoints
    Creates Asterisk endpoints for InternalNumbers that don't have them
    """
    from voip.models import InternalNumber, PsEndpoint
    
    results = {
        'created': 0,
        'updated': 0,
        'errors': []
    }
    
    internal_numbers = InternalNumber.objects.filter(active=True)
    
    for internal_number in internal_numbers:
        try:
            # Check if endpoint exists
            endpoint_exists = PsEndpoint.objects.using('asterisk').filter(
                id=internal_number.number
            ).exists()
            
            if not endpoint_exists:
                # Create endpoint
                result = auto_provision_endpoint(
                    user=internal_number.user,
                    extension_number=internal_number.number,
                    password=internal_number.password,
                    context='from-internal',
                    transport='transport-udp'
                )
                
                if result['success']:
                    results['created'] += 1
                else:
                    results['errors'].append({
                        'number': internal_number.number,
                        'error': result.get('error')
                    })
            else:
                results['updated'] += 1
                
        except Exception as e:
            logger.error(f"Error syncing internal number {internal_number.number}: {e}")
            results['errors'].append({
                'number': internal_number.number,
                'error': str(e)
            })
    
    logger.info(f"Sync completed: {results['created']} created, {results['updated']} existing, {len(results['errors'])} errors")
    return results


def generate_dialplan_for_endpoint(endpoint_id: str, context: str = 'from-internal'):
    """
    Generate basic dialplan extensions for an endpoint
    
    :param endpoint_id: Endpoint ID
    :param context: Dialplan context
    """
    from voip.models import Extension
    
    try:
        # Remove existing extensions for this endpoint
        Extension.objects.using('asterisk').filter(
            context=context,
            exten=endpoint_id
        ).delete()
        
        # Extension 1: Dial the endpoint with timeout
        Extension.objects.using('asterisk').create(
            context=context,
            exten=endpoint_id,
            priority=1,
            app='Dial',
            appdata=f'PJSIP/{endpoint_id},30,tT'
        )
        
        # Extension 2: If no answer, send to voicemail
        Extension.objects.using('asterisk').create(
            context=context,
            exten=endpoint_id,
            priority=2,
            app='VoiceMail',
            appdata=f'{endpoint_id}@default,u'
        )
        
        # Extension 3: Hangup
        Extension.objects.using('asterisk').create(
            context=context,
            exten=endpoint_id,
            priority=3,
            app='Hangup'
        )
        
        logger.info(f"Generated dialplan for endpoint {endpoint_id} in context {context}")
        
    except Exception as e:
        logger.error(f"Error generating dialplan for {endpoint_id}: {e}")


def sync_routing_rules_to_dialplan():
    """
    Synchronize CallRoutingRule models to Asterisk dialplan extensions
    """
    from voip.models import CallRoutingRule, Extension
    from django.db.models import Q
    
    results = {
        'created': 0,
        'deleted': 0,
        'errors': []
    }
    
    try:
        # Get all active routing rules
        rules = CallRoutingRule.objects.filter(active=True).order_by('priority')
        
        # Clear existing auto-generated routing extensions
        Extension.objects.using('asterisk').filter(
            context='from-pstn',
            app='Goto'
        ).delete()
        
        for rule in rules:
            try:
                # Determine extension pattern from rule
                if rule.called_number_pattern:
                    exten_pattern = rule.called_number_pattern.replace('^', '_').replace('$', '')
                else:
                    exten_pattern = '_X.'  # Match all
                
                # Create dialplan based on action
                if rule.action == 'route_to_number' and rule.target_number:
                    Extension.objects.using('asterisk').create(
                        context='from-pstn',
                        exten=exten_pattern,
                        priority=rule.priority,
                        app='Goto',
                        appdata=f'from-internal,{rule.target_number.number},1'
                    )
                    results['created'] += 1
                    
                elif rule.action == 'route_to_group' and rule.target_group:
                    # Route to first available member
                    Extension.objects.using('asterisk').create(
                        context='from-pstn',
                        exten=exten_pattern,
                        priority=rule.priority,
                        app='Queue',
                        appdata=f'group-{rule.target_group.id},t,,,300'
                    )
                    results['created'] += 1
                    
                elif rule.action == 'play_announcement' and rule.announcement_text:
                    Extension.objects.using('asterisk').create(
                        context='from-pstn',
                        exten=exten_pattern,
                        priority=rule.priority,
                        app='Playback',
                        appdata='announcement'
                    )
                    results['created'] += 1
                    
                elif rule.action == 'hangup':
                    Extension.objects.using('asterisk').create(
                        context='from-pstn',
                        exten=exten_pattern,
                        priority=rule.priority,
                        app='Hangup',
                        appdata='16'  # Normal clearing
                    )
                    results['created'] += 1
                    
            except Exception as e:
                logger.error(f"Error creating dialplan for rule {rule.name}: {e}")
                results['errors'].append({
                    'rule': rule.name,
                    'error': str(e)
                })
        
        logger.info(f"Routing sync completed: {results['created']} extensions created")
        return results
        
    except Exception as e:
        logger.error(f"Error syncing routing rules: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def create_queue_for_group(number_group):
    """
    Create Asterisk queue configuration for a NumberGroup
    
    :param number_group: NumberGroup instance
    """
    from voip.models import Extension
    
    try:
        queue_name = f'group-{number_group.id}'
        context = 'from-internal'
        
        # Create queue extension
        Extension.objects.using('asterisk').create(
            context=context,
            exten=f'8{number_group.id:03d}',  # e.g., 8001 for group 1
            priority=1,
            app='Answer'
        )
        
        Extension.objects.using('asterisk').create(
            context=context,
            exten=f'8{number_group.id:03d}',
            priority=2,
            app='Queue',
            appdata=f'{queue_name},{number_group.distribution_strategy[0]},,,'
                    f'{number_group.queue_timeout}'
        )
        
        Extension.objects.using('asterisk').create(
            context=context,
            exten=f'8{number_group.id:03d}',
            priority=3,
            app='Hangup'
        )
        
        logger.info(f"Created queue {queue_name} for group {number_group.name}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating queue for group {number_group.name}: {e}")
        return False


def bulk_provision_users(user_ids: List[int] = None, context: str = 'from-internal') -> Dict:
    """
    Bulk provision Asterisk endpoints for multiple users
    
    :param user_ids: List of user IDs (None = all users without endpoints)
    :param context: Dialplan context
    :return: Provisioning results
    """
    from voip.models import PsEndpoint
    
    results = {
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    # Get users to provision
    if user_ids:
        users = User.objects.filter(id__in=user_ids)
    else:
        # Get users without endpoints
        users_with_endpoints = PsEndpoint.objects.using('asterisk').filter(
            crm_user__isnull=False
        ).values_list('crm_user_id', flat=True)
        users = User.objects.exclude(id__in=users_with_endpoints).filter(is_active=True)
    
    for user in users:
        result = auto_provision_endpoint(user, context=context)
        if result['success']:
            results['success'] += 1
        else:
            results['failed'] += 1
            results['errors'].append({
                'user': user.username,
                'error': result.get('error')
            })
    
    logger.info(f"Bulk provisioning completed: {results['success']} success, {results['failed']} failed")
    return results


def cleanup_expired_contacts():
    """
    Remove expired contact registrations from database
    """
    from voip.models import PsContact
    import time
    
    current_time = int(time.time())
    
    try:
        expired = PsContact.objects.using('asterisk').filter(
            expiration_time__lt=current_time
        )
        count = expired.count()
        expired.delete()
        
        logger.info(f"Cleaned up {count} expired contacts")
        return count
        
    except Exception as e:
        logger.error(f"Error cleaning up expired contacts: {e}")
        return 0


def get_endpoint_statistics() -> Dict[str, Any]:
    """
    Get statistics about Asterisk endpoints
    
    :return: Dictionary with statistics
    """
    from voip.models import PsEndpoint, PsContact
    from django.db import models
    import time
    
    try:
        total_endpoints = PsEndpoint.objects.using('asterisk').count()
        
        # Count registered endpoints (those with non-expired contacts)
        current_time = int(time.time())
        active_contacts = PsContact.objects.using('asterisk').filter(
            expiration_time__gt=current_time
        )
        registered_endpoints = active_contacts.values('endpoint').distinct().count()
        
        # Count by context
        contexts = PsEndpoint.objects.using('asterisk').values('context').annotate(
            count=models.Count('id')
        )
        
        return {
            'total_endpoints': total_endpoints,
            'registered_endpoints': registered_endpoints,
            'unregistered_endpoints': total_endpoints - registered_endpoints,
            'contexts': list(contexts),
            'registration_rate': (registered_endpoints / total_endpoints * 100) if total_endpoints > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error getting endpoint statistics: {e}")
        return {
            'error': str(e)
        }


def validate_endpoint_config(endpoint_id: str) -> Dict[str, Any]:
    """
    Validate endpoint configuration
    
    :param endpoint_id: Endpoint ID to validate
    :return: Validation result
    """
    from voip.models import PsEndpoint, PsAuth, PsAor
    
    issues = []
    warnings = []
    
    try:
        # Check endpoint exists
        try:
            endpoint = PsEndpoint.objects.using('asterisk').get(id=endpoint_id)
        except PsEndpoint.DoesNotExist:
            return {
                'valid': False,
                'error': f'Endpoint {endpoint_id} does not exist'
            }
        
        # Check auth exists
        if endpoint.auth:
            try:
                PsAuth.objects.using('asterisk').get(id=endpoint.auth)
            except PsAuth.DoesNotExist:
                issues.append(f'Auth section {endpoint.auth} not found')
        else:
            warnings.append('No authentication configured')
        
        # Check AOR exists
        if endpoint.aors:
            aor_ids = [aor.strip() for aor in endpoint.aors.split(',')]
            for aor_id in aor_ids:
                try:
                    PsAor.objects.using('asterisk').get(id=aor_id)
                except PsAor.DoesNotExist:
                    issues.append(f'AOR {aor_id} not found')
        else:
            issues.append('No AOR configured')
        
        # Check codecs
        if not endpoint.allow or endpoint.allow == 'all':
            warnings.append('No specific codecs configured')
        
        # Check transport
        if not endpoint.transport:
            issues.append('No transport configured')
        
        return {
            'valid': len(issues) == 0,
            'endpoint_id': endpoint_id,
            'issues': issues,
            'warnings': warnings
        }
        
    except Exception as e:
        logger.error(f"Error validating endpoint {endpoint_id}: {e}")
        return {
            'valid': False,
            'error': str(e)
        }
