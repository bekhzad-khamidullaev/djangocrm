# -*- coding: utf-8 -*-
"""
Asterisk Real-time Backend for Django CRM
Manages Asterisk PBX through Real-time database and AMI interface
"""
__version__ = '1.0.0'

import logging
import secrets
import string
from typing import Dict, Optional, List, Any
from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


class AsteriskRealtimeAPI:
    """
    Backend for managing Asterisk PBX through Real-time database
    and Asterisk Manager Interface (AMI)
    """
    
    def __init__(self, **options):
        """
        Initialize Asterisk Real-time API
        
        :param options: Configuration options from settings.VOIP
        """
        self.options = options
        self.ami_host = options.get('ami_host', settings.ASTERISK_AMI.get('HOST', '127.0.0.1'))
        self.ami_port = options.get('ami_port', settings.ASTERISK_AMI.get('PORT', 5038))
        self.ami_username = options.get('ami_username', settings.ASTERISK_AMI.get('USERNAME', 'admin'))
        self.ami_secret = options.get('ami_secret', settings.ASTERISK_AMI.get('SECRET', ''))
        self.ami_timeout = options.get('ami_timeout', settings.ASTERISK_AMI.get('CONNECT_TIMEOUT', 5))
        
        # Default contexts and settings
        self.default_context = options.get('default_context', 'from-internal')
        self.default_transport = options.get('default_transport', 'transport-udp')
        self.external_ip = options.get('external_ip', '')
        self.local_net = options.get('local_net', '192.168.0.0/16')
        
        # Codec preferences
        self.default_codecs = options.get('codecs', 'ulaw,alaw,gsm,g722')
        
        # Auto-provisioning settings
        self.auto_provision = options.get('auto_provision', True)
        self.start_extension = options.get('start_extension', 1000)
        
        # AMI connection (lazy-loaded)
        self._ami_connection = None
    
    @property
    def ami(self):
        """Get or create AMI connection"""
        if self._ami_connection is None:
            self._ami_connection = self._connect_ami()
        return self._ami_connection
    
    def _connect_ami(self):
        """
        Connect to Asterisk Manager Interface
        Returns AMI connection object
        """
        try:
            from voip.integrations.asterisk import AsteriskAMI
            
            ami = AsteriskAMI(
                host=self.ami_host,
                port=self.ami_port,
                username=self.ami_username,
                secret=self.ami_secret,
                timeout=self.ami_timeout
            )
            
            if ami.connect():
                logger.info(f"Connected to Asterisk AMI at {self.ami_host}:{self.ami_port}")
                return ami
            else:
                logger.error(f"Failed to connect to Asterisk AMI")
                return None
                
        except Exception as e:
            logger.error(f"Error connecting to Asterisk AMI: {e}")
            return None
    
    def disconnect_ami(self):
        """Disconnect from AMI"""
        if self._ami_connection:
            try:
                self._ami_connection.disconnect()
                self._ami_connection = None
            except Exception as e:
                logger.error(f"Error disconnecting from AMI: {e}")
    
    # ========================================
    # Endpoint Management
    # ========================================
    
    def create_endpoint(self, endpoint_id: str, username: str, password: str = None,
                       context: str = None, callerid: str = None, 
                       transport: str = None, **kwargs) -> Dict[str, Any]:
        """
        Create a complete SIP endpoint with auth and AOR
        
        :param endpoint_id: Unique endpoint identifier (e.g., '1001')
        :param username: SIP username for authentication
        :param password: SIP password (auto-generated if not provided)
        :param context: Dialplan context (default: from-internal)
        :param callerid: Caller ID for this endpoint
        :param transport: Transport to use (default: transport-udp)
        :return: Dictionary with endpoint details
        """
        from voip.models import PsEndpoint, PsAuth, PsAor
        
        # Generate secure password if not provided
        if not password:
            password = self._generate_password()
        
        # Set defaults
        context = context or self.default_context
        transport = transport or self.default_transport
        
        try:
            with transaction.atomic(using='asterisk'):
                # Create Authentication
                auth = PsAuth.objects.using('asterisk').create(
                    id=endpoint_id,
                    auth_type='userpass',
                    username=username,
                    password=password,
                    **kwargs.get('auth_params', {})
                )
                
                # Create AOR (Address of Record)
                aor = PsAor.objects.using('asterisk').create(
                    id=endpoint_id,
                    max_contacts=kwargs.get('max_contacts', 1),
                    qualify_frequency=kwargs.get('qualify_frequency', 60),
                    **kwargs.get('aor_params', {})
                )
                
                # Create Endpoint
                endpoint = PsEndpoint.objects.using('asterisk').create(
                    id=endpoint_id,
                    transport=transport,
                    context=context,
                    aors=endpoint_id,
                    auth=endpoint_id,
                    callerid=callerid or f'"{username}" <{endpoint_id}>',
                    disallow='all',
                    allow=kwargs.get('codecs', self.default_codecs),
                    direct_media='no',
                    rtp_symmetric='yes',
                    force_rport='yes',
                    rewrite_contact='yes',
                    **kwargs.get('endpoint_params', {})
                )
                
                logger.info(f"Created endpoint {endpoint_id} with username {username}")
                
                # Reload PJSIP configuration via AMI
                self._reload_pjsip()
                
                return {
                    'success': True,
                    'endpoint_id': endpoint_id,
                    'username': username,
                    'password': password,
                    'context': context,
                    'transport': transport,
                    'sip_uri': f'sip:{username}@{self.ami_host}'
                }
                
        except Exception as e:
            logger.error(f"Error creating endpoint {endpoint_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def update_endpoint(self, endpoint_id: str, **kwargs) -> Dict[str, Any]:
        """
        Update existing endpoint configuration
        
        :param endpoint_id: Endpoint ID to update
        :param kwargs: Fields to update
        :return: Success status
        """
        from voip.models import PsEndpoint, PsAuth, PsAor
        
        try:
            with transaction.atomic(using='asterisk'):
                updated = []
                
                # Update endpoint
                if 'endpoint_params' in kwargs:
                    endpoint = PsEndpoint.objects.using('asterisk').get(id=endpoint_id)
                    for key, value in kwargs['endpoint_params'].items():
                        setattr(endpoint, key, value)
                    endpoint.save(using='asterisk')
                    updated.append('endpoint')
                
                # Update auth
                if 'auth_params' in kwargs:
                    auth = PsAuth.objects.using('asterisk').get(id=endpoint_id)
                    for key, value in kwargs['auth_params'].items():
                        setattr(auth, key, value)
                    auth.save(using='asterisk')
                    updated.append('auth')
                
                # Update AOR
                if 'aor_params' in kwargs:
                    aor = PsAor.objects.using('asterisk').get(id=endpoint_id)
                    for key, value in kwargs['aor_params'].items():
                        setattr(aor, key, value)
                    aor.save(using='asterisk')
                    updated.append('aor')
                
                self._reload_pjsip()
                
                logger.info(f"Updated endpoint {endpoint_id}: {', '.join(updated)}")
                
                return {
                    'success': True,
                    'endpoint_id': endpoint_id,
                    'updated': updated
                }
                
        except Exception as e:
            logger.error(f"Error updating endpoint {endpoint_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_endpoint(self, endpoint_id: str) -> Dict[str, Any]:
        """
        Delete endpoint and associated auth/AOR
        
        :param endpoint_id: Endpoint ID to delete
        :return: Success status
        """
        from voip.models import PsEndpoint, PsAuth, PsAor
        
        try:
            with transaction.atomic(using='asterisk'):
                # Delete in reverse order
                PsEndpoint.objects.using('asterisk').filter(id=endpoint_id).delete()
                PsAor.objects.using('asterisk').filter(id=endpoint_id).delete()
                PsAuth.objects.using('asterisk').filter(id=endpoint_id).delete()
                
                self._reload_pjsip()
                
                logger.info(f"Deleted endpoint {endpoint_id}")
                
                return {
                    'success': True,
                    'endpoint_id': endpoint_id
                }
                
        except Exception as e:
            logger.error(f"Error deleting endpoint {endpoint_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_endpoint_status(self, endpoint_id: str) -> Dict[str, Any]:
        """
        Get endpoint registration status via AMI
        
        :param endpoint_id: Endpoint ID
        :return: Status information
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        try:
            # Get endpoint details via AMI
            response = self.ami.send_action({
                'Action': 'PJSIPShowEndpoint',
                'Endpoint': endpoint_id
            })
            
            # Get contact status
            contacts = self.ami.send_action({
                'Action': 'PJSIPShowContacts',
                'Endpoint': endpoint_id
            })
            
            return {
                'success': True,
                'endpoint_id': endpoint_id,
                'registered': len(contacts.get('contacts', [])) > 0,
                'contacts': contacts.get('contacts', []),
                'details': response
            }
            
        except Exception as e:
            logger.error(f"Error getting endpoint status for {endpoint_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ========================================
    # Dialplan Management
    # ========================================
    
    def create_extension(self, context: str, exten: str, priority: int,
                        app: str, appdata: str = '') -> Dict[str, Any]:
        """
        Create dialplan extension
        
        :param context: Dialplan context
        :param exten: Extension pattern
        :param priority: Priority number
        :param app: Application to execute
        :param appdata: Application arguments
        :return: Success status
        """
        from voip.models import Extension
        
        try:
            extension = Extension.objects.using('asterisk').create(
                context=context,
                exten=exten,
                priority=priority,
                app=app,
                appdata=appdata
            )
            
            # Reload dialplan
            self._reload_dialplan()
            
            logger.info(f"Created extension: {context},{exten},{priority}")
            
            return {
                'success': True,
                'extension_id': extension.id
            }
            
        except Exception as e:
            logger.error(f"Error creating extension: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def generate_dialplan_for_endpoint(self, endpoint_id: str, context: str = None) -> List[Dict]:
        """
        Generate basic dialplan for an endpoint
        
        :param endpoint_id: Endpoint ID
        :param context: Context to create extensions in
        :return: List of created extensions
        """
        context = context or self.default_context
        extensions = []
        
        try:
            # Extension for dialing this endpoint
            ext = self.create_extension(
                context=context,
                exten=endpoint_id,
                priority=1,
                app='Dial',
                appdata=f'PJSIP/{endpoint_id},20'
            )
            if ext['success']:
                extensions.append(ext)
            
            # Voicemail if no answer
            ext = self.create_extension(
                context=context,
                exten=endpoint_id,
                priority=2,
                app='VoiceMail',
                appdata=f'{endpoint_id}@default'
            )
            if ext['success']:
                extensions.append(ext)
            
            return extensions
            
        except Exception as e:
            logger.error(f"Error generating dialplan for {endpoint_id}: {e}")
            return []
    
    # ========================================
    # Call Control (AMI Operations)
    # ========================================
    
    def originate_call(self, from_endpoint: str, to_number: str,
                      callerid: str = None, variables: Dict = None) -> Dict[str, Any]:
        """
        Initiate a call from endpoint to number via AMI
        
        :param from_endpoint: Endpoint ID to call from
        :param to_number: Number to dial
        :param callerid: Caller ID to use
        :param variables: Channel variables
        :return: Call status
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        try:
            action = {
                'Action': 'Originate',
                'Channel': f'PJSIP/{from_endpoint}',
                'Exten': to_number,
                'Context': self.default_context,
                'Priority': '1',
                'Timeout': '30000',
                'Async': 'true'
            }
            
            if callerid:
                action['CallerID'] = callerid
            
            if variables:
                # Convert dict to Asterisk variable format
                var_str = ','.join([f'{k}={v}' for k, v in variables.items()])
                action['Variable'] = var_str
            
            response = self.ami.send_action(action)
            
            logger.info(f"Originated call from {from_endpoint} to {to_number}")
            
            return {
                'success': True,
                'from': from_endpoint,
                'to': to_number,
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error originating call: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def hangup_channel(self, channel: str, cause: int = 16) -> Dict[str, Any]:
        """
        Hangup a channel
        
        :param channel: Channel name
        :param cause: Hangup cause code
        :return: Success status
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        try:
            response = self.ami.send_action({
                'Action': 'Hangup',
                'Channel': channel,
                'Cause': str(cause)
            })
            
            logger.info(f"Hung up channel {channel}")
            
            return {
                'success': True,
                'channel': channel,
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error hanging up channel: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_channel_status(self, channel: str = None) -> Dict[str, Any]:
        """
        Get status of channel(s)
        
        :param channel: Specific channel (None for all)
        :return: Channel status
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        try:
            action = {'Action': 'CoreShowChannels'}
            if channel:
                action['Channel'] = channel
            
            response = self.ami.send_action(action)
            
            return {
                'success': True,
                'channels': response.get('channels', [])
            }
            
        except Exception as e:
            logger.error(f"Error getting channel status: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ========================================
    # Advanced Call Operations
    # ========================================
    
    def transfer_call(self, channel: str, exten: str, context: str = None) -> Dict[str, Any]:
        """
        Transfer call to another extension
        
        :param channel: Channel to transfer
        :param exten: Extension to transfer to
        :param context: Context (default: from-internal)
        :return: Success status
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        context = context or self.default_context
        
        try:
            response = self.ami.send_action({
                'Action': 'Redirect',
                'Channel': channel,
                'Exten': exten,
                'Context': context,
                'Priority': '1'
            })
            
            logger.info(f"Transferred channel {channel} to {exten}")
            
            return {
                'success': True,
                'channel': channel,
                'exten': exten,
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error transferring call: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def park_call(self, channel: str, parking_lot: str = 'default') -> Dict[str, Any]:
        """
        Park a call
        
        :param channel: Channel to park
        :param parking_lot: Parking lot name
        :return: Parking space information
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        try:
            response = self.ami.send_action({
                'Action': 'Park',
                'Channel': channel,
                'ParkingLot': parking_lot
            })
            
            logger.info(f"Parked channel {channel}")
            
            return {
                'success': True,
                'channel': channel,
                'parking_space': response.get('ParkingSpace'),
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error parking call: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def start_recording(self, channel: str, filename: str = None, 
                       format: str = 'wav', mix: bool = True) -> Dict[str, Any]:
        """
        Start recording a call
        
        :param channel: Channel to record
        :param filename: Recording filename (auto-generated if not provided)
        :param format: Recording format (wav/gsm/wav49)
        :param mix: Mix both channels
        :return: Recording information
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        if not filename:
            import time
            filename = f"recording-{int(time.time())}"
        
        try:
            response = self.ami.send_action({
                'Action': 'MixMonitor',
                'Channel': channel,
                'File': f'{filename}.{format}',
                'Options': 'b' if mix else ''
            })
            
            logger.info(f"Started recording channel {channel} to {filename}.{format}")
            
            return {
                'success': True,
                'channel': channel,
                'filename': f'{filename}.{format}',
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def stop_recording(self, channel: str) -> Dict[str, Any]:
        """
        Stop recording a call
        
        :param channel: Channel to stop recording
        :return: Success status
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        try:
            response = self.ami.send_action({
                'Action': 'StopMixMonitor',
                'Channel': channel
            })
            
            logger.info(f"Stopped recording channel {channel}")
            
            return {
                'success': True,
                'channel': channel,
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ========================================
    # Queue Management
    # ========================================
    
    def get_queue_status(self, queue: str = None) -> Dict[str, Any]:
        """
        Get status of queue(s)
        
        :param queue: Specific queue name (None for all)
        :return: Queue status
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        try:
            action = {'Action': 'QueueStatus'}
            if queue:
                action['Queue'] = queue
            
            response = self.ami.send_action(action)
            
            return {
                'success': True,
                'queues': response.get('queues', [])
            }
            
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def add_queue_member(self, queue: str, interface: str, 
                        member_name: str = None, penalty: int = 0) -> Dict[str, Any]:
        """
        Add member to queue
        
        :param queue: Queue name
        :param interface: Interface (e.g., PJSIP/1001)
        :param member_name: Member display name
        :param penalty: Member penalty
        :return: Success status
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        try:
            action = {
                'Action': 'QueueAdd',
                'Queue': queue,
                'Interface': interface,
                'Penalty': str(penalty)
            }
            
            if member_name:
                action['MemberName'] = member_name
            
            response = self.ami.send_action(action)
            
            logger.info(f"Added {interface} to queue {queue}")
            
            return {
                'success': True,
                'queue': queue,
                'interface': interface,
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error adding queue member: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def remove_queue_member(self, queue: str, interface: str) -> Dict[str, Any]:
        """
        Remove member from queue
        
        :param queue: Queue name
        :param interface: Interface to remove
        :return: Success status
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        try:
            response = self.ami.send_action({
                'Action': 'QueueRemove',
                'Queue': queue,
                'Interface': interface
            })
            
            logger.info(f"Removed {interface} from queue {queue}")
            
            return {
                'success': True,
                'queue': queue,
                'interface': interface,
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error removing queue member: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ========================================
    # Database Operations
    # ========================================
    
    def db_put(self, family: str, key: str, value: str) -> Dict[str, Any]:
        """
        Put value in Asterisk database
        
        :param family: Database family
        :param key: Key name
        :param value: Value to store
        :return: Success status
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        try:
            response = self.ami.send_action({
                'Action': 'DBPut',
                'Family': family,
                'Key': key,
                'Val': value
            })
            
            return {
                'success': True,
                'family': family,
                'key': key,
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error putting value in Asterisk DB: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def db_get(self, family: str, key: str) -> Dict[str, Any]:
        """
        Get value from Asterisk database
        
        :param family: Database family
        :param key: Key name
        :return: Value and success status
        """
        if not self.ami:
            return {'success': False, 'error': 'AMI not connected'}
        
        try:
            response = self.ami.send_action({
                'Action': 'DBGet',
                'Family': family,
                'Key': key
            })
            
            return {
                'success': True,
                'family': family,
                'key': key,
                'value': response.get('Val'),
                'response': response
            }
            
        except Exception as e:
            logger.error(f"Error getting value from Asterisk DB: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    # ========================================
    # Utility Methods
    # ========================================
    
    def _reload_pjsip(self):
        """Reload PJSIP configuration"""
        if self.ami:
            try:
                self.ami.send_action({
                    'Action': 'PJSIPReload'
                })
                logger.info("Reloaded PJSIP configuration")
            except Exception as e:
                logger.error(f"Error reloading PJSIP: {e}")
    
    def _reload_dialplan(self):
        """Reload dialplan"""
        if self.ami:
            try:
                self.ami.send_action({
                    'Action': 'DialplanReload'
                })
                logger.info("Reloaded dialplan")
            except Exception as e:
                logger.error(f"Error reloading dialplan: {e}")
    
    def _generate_password(self, length: int = 16) -> str:
        """
        Generate secure random password
        
        :param length: Password length
        :return: Random password
        """
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test AMI connection and database access
        
        :return: Connection status
        """
        result = {
            'ami_connected': False,
            'database_accessible': False,
            'asterisk_version': None
        }
        
        # Test AMI
        if self.ami:
            try:
                response = self.ami.send_action({'Action': 'CoreShowVersion'})
                result['ami_connected'] = True
                result['asterisk_version'] = response.get('CoreShowVersion', 'Unknown')
            except Exception as e:
                logger.error(f"AMI test failed: {e}")
        
        # Test database
        try:
            from voip.models import PsEndpoint
            count = PsEndpoint.objects.using('asterisk').count()
            result['database_accessible'] = True
            result['endpoint_count'] = count
        except Exception as e:
            logger.error(f"Database test failed: {e}")
        
        return result
    
    def make_query(self, from_num: str, to_num: str, endpoint: str = None):
        """
        Compatibility method for making calls (used by callback view)
        
        :param from_num: Source number/endpoint
        :param to_num: Destination number
        :param endpoint: Specific endpoint to use
        :return: Call result
        """
        endpoint_id = endpoint or from_num
        return self.originate_call(endpoint_id, to_num)
