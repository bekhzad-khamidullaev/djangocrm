"""
Call Initiator Utility for Cold Calls
Handles actual call initiation through VoIP providers
"""
from __future__ import annotations

import logging
import requests
from typing import Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)


class CallInitiator:
    """
    Initiates outbound calls through configured VoIP providers
    Supports: Asterisk AMI, OnlinePBX, FreeSWITCH
    """
    
    def __init__(self):
        self.voip_config = getattr(settings, 'VOIP', [])
        self.default_provider = self._get_default_provider()
    
    def _get_default_provider(self) -> str:
        """Get the default VoIP provider"""
        if self.voip_config:
            return self.voip_config[0].get('PROVIDER', 'asterisk')
        return 'asterisk'
    
    def make_call(self, from_number: str, to_number: str, 
                  call_id: int = 0, campaign_id: int = None) -> Dict[str, Any]:
        """
        Initiate a call through the VoIP provider
        
        Args:
            from_number: Caller ID / Extension to use
            to_number: Phone number to dial
            call_id: ColdCall ID for tracking
            campaign_id: Optional campaign ID
        
        Returns:
            Dict with success status and session_id or error
        """
        provider = self.default_provider.lower()
        
        logger.info(f"Making call via {provider}: {from_number} -> {to_number}")
        
        if provider == 'asterisk':
            return self._make_call_asterisk(from_number, to_number, call_id, campaign_id)
        elif provider == 'onlinepbx':
            return self._make_call_onlinepbx(from_number, to_number, call_id, campaign_id)
        elif provider == 'freeswitch':
            return self._make_call_freeswitch(from_number, to_number, call_id, campaign_id)
        else:
            logger.error(f"Unsupported provider: {provider}")
            return {
                'success': False,
                'error': f'Unsupported provider: {provider}'
            }
    
    def _make_call_asterisk(self, from_number: str, to_number: str, 
                            call_id: int, campaign_id: int) -> Dict[str, Any]:
        """
        Make call through Asterisk AMI
        Uses Originate command to create outbound call
        """
        try:
            from voip.integrations.asterisk import AsteriskAMI
            
            # Get AMI connection
            ami_config = getattr(settings, 'ASTERISK_AMI', {})
            ami = AsteriskAMI(
                host=ami_config.get('HOST', '127.0.0.1'),
                port=ami_config.get('PORT', 5038),
                username=ami_config.get('USERNAME', 'admin'),
                secret=ami_config.get('SECRET', ''),
            )
            
            if not ami.connect():
                return {
                    'success': False,
                    'error': 'Failed to connect to Asterisk AMI'
                }
            
            # Originate call
            # Channel: Where to place the call (e.g., SIP/1001)
            # Exten: Extension to connect to
            # Context: Dialplan context
            # Priority: Dialplan priority
            # CallerID: Caller ID to present
            
            result = ami.originate(
                channel=f'SIP/{from_number}',
                exten=to_number,
                context='from-internal',  # Adjust based on your dialplan
                priority=1,
                caller_id=from_number,
                variables={
                    'CALL_ID': call_id,
                    'CAMPAIGN_ID': campaign_id or '',
                    'COLD_CALL': 'true'
                }
            )
            
            ami.disconnect()
            
            if result.get('Response') == 'Success':
                return {
                    'success': True,
                    'session_id': result.get('ActionID', f'ast-{call_id}'),
                    'provider': 'asterisk'
                }
            else:
                return {
                    'success': False,
                    'error': result.get('Message', 'Originate failed')
                }
                
        except Exception as e:
            logger.error(f"Asterisk call failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _make_call_onlinepbx(self, from_number: str, to_number: str,
                             call_id: int, campaign_id: int) -> Dict[str, Any]:
        """
        Make call through OnlinePBX API
        """
        try:
            from voip.models import OnlinePBXSettings
            from voip.backends.onlinepbxbackend import OnlinePBXBackend
            
            settings_obj = OnlinePBXSettings.get_solo()
            backend = OnlinePBXBackend(settings_obj)
            
            # Make call through OnlinePBX API
            result = backend.originate_call(
                from_extension=from_number,
                to_number=to_number,
                caller_id=from_number
            )
            
            if result.get('status') == 'success':
                return {
                    'success': True,
                    'session_id': result.get('call_id', f'onpbx-{call_id}'),
                    'provider': 'onlinepbx'
                }
            else:
                return {
                    'success': False,
                    'error': result.get('message', 'Call failed')
                }
                
        except Exception as e:
            logger.error(f"OnlinePBX call failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _make_call_freeswitch(self, from_number: str, to_number: str,
                              call_id: int, campaign_id: int) -> Dict[str, Any]:
        """
        Make call through FreeSWITCH ESL (Event Socket Library)
        """
        try:
            from voip.integrations.freeswitch import FreeSWITCHESL
            
            # Get FreeSWITCH connection
            fs_config = getattr(settings, 'FREESWITCH_ESL', {})
            esl = FreeSWITCHESL(
                host=fs_config.get('HOST', '127.0.0.1'),
                port=fs_config.get('PORT', 8021),
                password=fs_config.get('PASSWORD', 'ClueCon'),
            )
            
            if not esl.connect():
                return {
                    'success': False,
                    'error': 'Failed to connect to FreeSWITCH ESL'
                }
            
            # Originate call
            result = esl.originate(
                endpoint=f'user/{from_number}',
                destination=to_number,
                caller_id_number=from_number,
                variables={
                    'call_id': call_id,
                    'campaign_id': campaign_id or '',
                    'cold_call': 'true'
                }
            )
            
            esl.disconnect()
            
            if result.get('success'):
                return {
                    'success': True,
                    'session_id': result.get('uuid', f'fs-{call_id}'),
                    'provider': 'freeswitch'
                }
            else:
                return {
                    'success': False,
                    'error': result.get('error', 'Originate failed')
                }
                
        except Exception as e:
            logger.error(f"FreeSWITCH call failed: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def check_call_status(self, session_id: str) -> Dict[str, Any]:
        """
        Check the status of an ongoing call
        
        Args:
            session_id: Call session identifier
        
        Returns:
            Dict with call status information
        """
        provider = self.default_provider.lower()
        
        if provider == 'asterisk':
            return self._check_asterisk_status(session_id)
        elif provider == 'onlinepbx':
            return self._check_onlinepbx_status(session_id)
        elif provider == 'freeswitch':
            return self._check_freeswitch_status(session_id)
        else:
            return {
                'success': False,
                'error': 'Provider not supported'
            }
    
    def _check_asterisk_status(self, session_id: str) -> Dict[str, Any]:
        """Check call status in Asterisk"""
        try:
            from voip.integrations.asterisk import AsteriskAMI
            
            ami_config = getattr(settings, 'ASTERISK_AMI', {})
            ami = AsteriskAMI(
                host=ami_config.get('HOST', '127.0.0.1'),
                port=ami_config.get('PORT', 5038),
                username=ami_config.get('USERNAME', 'admin'),
                secret=ami_config.get('SECRET', ''),
            )
            
            if not ami.connect():
                return {'success': False, 'error': 'AMI connection failed'}
            
            # Get channel status
            result = ami.command('core show channels')
            
            ami.disconnect()
            
            return {
                'success': True,
                'status': 'active' if session_id in str(result) else 'completed'
            }
            
        except Exception as e:
            logger.error(f"Status check failed: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def _check_onlinepbx_status(self, session_id: str) -> Dict[str, Any]:
        """Check call status in OnlinePBX"""
        # Implement OnlinePBX status check
        return {'success': True, 'status': 'unknown'}
    
    def _check_freeswitch_status(self, session_id: str) -> Dict[str, Any]:
        """Check call status in FreeSWITCH"""
        # Implement FreeSWITCH status check
        return {'success': True, 'status': 'unknown'}
