"""
ViewSets for SMS API endpoints - wrapping existing SMS functionality
"""
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from integrations.models import ChannelAccount, ExternalMessage
from integrations.views_sms import SendSMSView


@extend_schema(tags=['SMS'])
class SMSViewSet(viewsets.ViewSet):
    """
    API endpoints for SMS operations
    Wraps existing SMS functionality from integrations app
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'])
    def send(self, request):
        """
        Send single SMS
        
        Required fields:
        - channel_id: ID of the SMS provider channel
        - to: Phone number
        - text: Message content
        - async: (optional) Send asynchronously via Celery (default: true)
        """
        # Delegate to existing SendSMSView
        view = SendSMSView()
        return view.post(request)
    
    @action(detail=False, methods=['post'])
    def send_bulk(self, request):
        """
        Send SMS to multiple recipients
        
        Required fields:
        - channel_id: ID of the SMS provider channel
        - phone_numbers: List of phone numbers
        - text: Message content
        """
        channel_id = request.data.get('channel_id')
        phone_numbers = request.data.get('phone_numbers', [])
        text = request.data.get('text', '').strip()
        
        if not all([channel_id, phone_numbers, text]):
            return Response({'error': 'Missing required fields: channel_id, phone_numbers, text'}, status=400)
        
        if not isinstance(phone_numbers, list):
            return Response({'error': 'phone_numbers must be a list'}, status=400)
        
        # Queue messages using Celery
        try:
            from integrations.tasks import send_sms_task
            task_ids = []
            for phone in phone_numbers:
                task = send_sms_task.delay(channel_id, phone, text)
                task_ids.append(str(task.id))
            
            return Response({
                'status': 'queued',
                'count': len(phone_numbers),
                'task_ids': task_ids
            })
        except ImportError:
            # Fallback if Celery task not defined
            return Response({
                'error': 'Bulk SMS requires Celery task configuration'
            }, status=500)
    
    @action(detail=False, methods=['get'])
    def history(self, request):
        """
        Get SMS history
        
        Query params:
        - limit: Number of messages to return (default: 50)
        - channel_id: Filter by channel
        """
        limit = int(request.query_params.get('limit', 50))
        channel_id = request.query_params.get('channel_id')
        
        messages = ExternalMessage.objects.filter(
            channel__type__in=['eskiz', 'playmobile'],
            direction='out'
        )
        
        if channel_id:
            messages = messages.filter(channel_id=channel_id)
        
        messages = messages.order_by('-created_at')[:limit]
        
        data = [{
            'id': msg.id,
            'phone': msg.recipient_id,
            'text': msg.text,
            'status': msg.status,
            'sent_at': msg.created_at.isoformat() if msg.created_at else None,
            'provider': msg.channel.get_type_display() if msg.channel else None,
            'provider_id': msg.external_id
        } for msg in messages]
        
        return Response({'results': data, 'count': len(data)})
    
    @action(detail=False, methods=['get'])
    def providers(self, request):
        """
        List available SMS providers
        """
        channels = ChannelAccount.objects.filter(
            type__in=['eskiz', 'playmobile'],
            is_active=True
        )
        
        data = [{
            'id': ch.id,
            'name': ch.name or ch.get_type_display(),
            'type': ch.type,
            'type_display': ch.get_type_display()
        } for ch in channels]
        
        return Response({'results': data, 'count': len(data)})
    
    @action(detail=False, methods=['get'])
    def status(self, request):
        """
        Get SMS service status and statistics
        """
        total_sent = ExternalMessage.objects.filter(
            channel__type__in=['eskiz', 'playmobile'],
            direction='out',
            status='SENT'
        ).count()
        
        total_failed = ExternalMessage.objects.filter(
            channel__type__in=['eskiz', 'playmobile'],
            direction='out',
            status='FAILED'
        ).count()
        
        active_providers = ChannelAccount.objects.filter(
            type__in=['eskiz', 'playmobile'],
            is_active=True
        ).count()
        
        return Response({
            'status': 'operational' if active_providers > 0 else 'no_providers',
            'active_providers': active_providers,
            'total_sent': total_sent,
            'total_failed': total_failed
        })
