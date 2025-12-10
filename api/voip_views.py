"""
VoIP and Cold Call API endpoints
"""
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from voip.models import CallLog, CallQueue, IncomingCall, Connection
from voip.tasks import (
    initiate_cold_call, schedule_cold_call, 
    bulk_schedule_cold_calls
)


@extend_schema(tags=['VoIP & Cold Calls'])
class VoIPViewSet(viewsets.ViewSet):
    """
    API endpoints for VoIP operations including cold calls
    """
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['post'], url_path='cold-call/initiate')
    def initiate_call(self, request):
        """
        Initiate a cold call immediately
        
        Required fields:
        - to_number: Phone number to call
        - from_number: (optional) Caller ID to use
        - lead_id: (optional) Lead ID
        - contact_id: (optional) Contact ID
        - campaign_id: (optional) Campaign ID
        """
        to_number = request.data.get('to_number')
        from_number = request.data.get('from_number', '1000')
        lead_id = request.data.get('lead_id')
        contact_id = request.data.get('contact_id')
        campaign_id = request.data.get('campaign_id')
        
        if not to_number:
            return Response({'error': 'to_number is required'}, status=400)
        
        # Schedule immediate call
        task = initiate_cold_call.delay(
            call_id=0,
            from_number=from_number,
            to_number=to_number,
            campaign_id=campaign_id
        )
        
        return Response({
            'status': 'initiated',
            'task_id': task.id,
            'to_number': to_number,
            'from_number': from_number
        })
    
    @action(detail=False, methods=['post'], url_path='cold-call/schedule')
    def schedule_call(self, request):
        """
        Schedule a cold call for later
        
        Required fields:
        - to_number OR lead_id OR contact_id
        
        Optional fields:
        - from_number: Caller ID to use
        - scheduled_time: ISO format datetime (e.g., "2024-01-15T14:30:00Z")
        - campaign_id: Campaign ID
        """
        to_number = request.data.get('to_number')
        lead_id = request.data.get('lead_id')
        contact_id = request.data.get('contact_id')
        from_number = request.data.get('from_number')
        scheduled_time = request.data.get('scheduled_time')
        campaign_id = request.data.get('campaign_id')
        
        if not any([to_number, lead_id, contact_id]):
            return Response({
                'error': 'One of to_number, lead_id, or contact_id is required'
            }, status=400)
        
        # Schedule call
        task = schedule_cold_call.delay(
            lead_id=lead_id,
            contact_id=contact_id,
            phone_number=to_number,
            scheduled_time=scheduled_time,
            campaign_id=campaign_id,
            from_number=from_number
        )
        
        return Response({
            'status': 'scheduled',
            'task_id': task.id,
            'scheduled_time': scheduled_time,
            'message': 'Call scheduled successfully'
        })
    
    @action(detail=False, methods=['post'], url_path='cold-call/bulk')
    def bulk_schedule_calls(self, request):
        """
        Schedule multiple cold calls in bulk
        
        Required fields:
        - phone_numbers: List of phone numbers
        
        Optional fields:
        - from_number: Caller ID to use
        - campaign_id: Campaign ID
        - delay_between_calls: Seconds between calls (default: 30)
        """
        phone_numbers = request.data.get('phone_numbers', [])
        from_number = request.data.get('from_number')
        campaign_id = request.data.get('campaign_id')
        delay_between_calls = int(request.data.get('delay_between_calls', 30))
        
        if not phone_numbers or not isinstance(phone_numbers, list):
            return Response({
                'error': 'phone_numbers must be a non-empty list'
            }, status=400)
        
        # Schedule bulk calls
        task = bulk_schedule_cold_calls.delay(
            phone_numbers=phone_numbers,
            campaign_id=campaign_id,
            from_number=from_number,
            delay_between_calls=delay_between_calls
        )
        
        return Response({
            'status': 'scheduled',
            'task_id': task.id,
            'total_numbers': len(phone_numbers),
            'delay_between_calls': delay_between_calls,
            'message': f'{len(phone_numbers)} calls scheduled'
        })
    
    @action(detail=False, methods=['get'], url_path='call-logs')
    def call_logs(self, request):
        """
        Get call logs with filtering
        
        Query params:
        - direction: inbound/outbound/internal
        - status: ringing/answered/busy/no_answer/failed
        - limit: Number of records (default: 50)
        - date_from: ISO datetime
        - date_to: ISO datetime
        """
        direction = request.query_params.get('direction')
        status = request.query_params.get('status')
        limit = int(request.query_params.get('limit', 50))
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        
        queryset = CallLog.objects.all()
        
        if direction:
            queryset = queryset.filter(direction=direction)
        if status:
            queryset = queryset.filter(status=status)
        if date_from:
            queryset = queryset.filter(start_time__gte=date_from)
        if date_to:
            queryset = queryset.filter(start_time__lte=date_to)
        
        queryset = queryset.order_by('-start_time')[:limit]
        
        data = [{
            'id': log.id,
            'session_id': log.session_id,
            'caller_id': log.caller_id,
            'called_number': log.called_number,
            'direction': log.direction,
            'status': log.status,
            'start_time': log.start_time.isoformat() if log.start_time else None,
            'answer_time': log.answer_time.isoformat() if log.answer_time else None,
            'end_time': log.end_time.isoformat() if log.end_time else None,
            'duration': log.duration,
            'notes': log.notes
        } for log in queryset]
        
        return Response({
            'results': data,
            'count': len(data)
        })
    
    @action(detail=False, methods=['get'], url_path='call-logs/(?P<log_id>[0-9]+)')
    def call_log_detail(self, request, log_id=None):
        """
        Get detailed information about a specific call
        """
        try:
            log = CallLog.objects.get(id=log_id)
            
            return Response({
                'id': log.id,
                'session_id': log.session_id,
                'caller_id': log.caller_id,
                'called_number': log.called_number,
                'direction': log.direction,
                'status': log.status,
                'start_time': log.start_time.isoformat() if log.start_time else None,
                'answer_time': log.answer_time.isoformat() if log.answer_time else None,
                'end_time': log.end_time.isoformat() if log.end_time else None,
                'duration': log.duration,
                'call_duration': log.call_duration,
                'total_duration': log.total_duration,
                'queue_wait_time': log.queue_wait_time,
                'routed_to_number': log.routed_to_number.number if log.routed_to_number else None,
                'routed_to_group': log.routed_to_group.name if log.routed_to_group else None,
                'user_agent': log.user_agent,
                'codec': log.codec,
                'recording_file': log.recording_file,
                'notes': log.notes
            })
        except CallLog.DoesNotExist:
            return Response({'error': 'Call log not found'}, status=404)
    
    @action(detail=False, methods=['get'], url_path='call-queue')
    def call_queue(self, request):
        """
        Get current call queue status
        """
        queues = CallQueue.objects.filter(status='waiting').order_by('queue_position')
        
        data = [{
            'id': q.id,
            'group': q.group.name,
            'caller_id': q.caller_id,
            'called_number': q.called_number,
            'queue_position': q.queue_position,
            'wait_time': q.wait_time,
            'estimated_wait_time': q.estimated_wait_time,
            'status': q.status
        } for q in queues]
        
        return Response({
            'results': data,
            'count': len(data)
        })
    
    @action(detail=False, methods=['get'], url_path='incoming-calls')
    def incoming_calls(self, request):
        """
        Get recent incoming calls for current user
        """
        limit = int(request.query_params.get('limit', 20))
        
        calls = IncomingCall.objects.filter(
            user=request.user
        ).order_by('-created_at')[:limit]
        
        data = [{
            'id': call.id,
            'caller_id': call.caller_id,
            'client_name': call.client_name,
            'client_type': call.client_type,
            'client_id': call.client_id,
            'client_url': call.client_url,
            'is_consumed': call.is_consumed,
            'created_at': call.created_at.isoformat()
        } for call in calls]
        
        return Response({
            'results': data,
            'count': len(data)
        })
    
    @action(detail=False, methods=['get'], url_path='connections')
    def connections(self, request):
        """
        Get VoIP connections for current user
        """
        connections = Connection.objects.filter(
            owner=request.user,
            active=True
        )
        
        data = [{
            'id': conn.id,
            'type': conn.type,
            'number': conn.number,
            'callerid': conn.callerid,
            'provider': conn.provider,
            'active': conn.active
        } for conn in connections]
        
        return Response({
            'results': data,
            'count': len(data)
        })
    
    @action(detail=False, methods=['get'], url_path='call-statistics')
    def call_statistics(self, request):
        """
        Get call statistics for dashboard
        
        Query params:
        - period: today/week/month (default: today)
        """
        from django.db.models import Count, Avg, Sum
        from django.utils import timezone
        from datetime import timedelta
        
        period = request.query_params.get('period', 'today')
        
        # Calculate date range
        now = timezone.now()
        if period == 'today':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == 'week':
            start_date = now - timedelta(days=7)
        elif period == 'month':
            start_date = now - timedelta(days=30)
        else:
            start_date = now - timedelta(days=1)
        
        # Get statistics
        total_calls = CallLog.objects.filter(start_time__gte=start_date).count()
        
        answered_calls = CallLog.objects.filter(
            start_time__gte=start_date,
            status='answered'
        ).count()
        
        missed_calls = CallLog.objects.filter(
            start_time__gte=start_date,
            status__in=['no_answer', 'busy']
        ).count()
        
        avg_duration = CallLog.objects.filter(
            start_time__gte=start_date,
            status='answered',
            duration__isnull=False
        ).aggregate(avg_duration=Avg('duration'))['avg_duration'] or 0
        
        # Call direction breakdown
        inbound = CallLog.objects.filter(
            start_time__gte=start_date,
            direction='inbound'
        ).count()
        
        outbound = CallLog.objects.filter(
            start_time__gte=start_date,
            direction='outbound'
        ).count()
        
        return Response({
            'period': period,
            'start_date': start_date.isoformat(),
            'total_calls': total_calls,
            'answered_calls': answered_calls,
            'missed_calls': missed_calls,
            'answer_rate': round(answered_calls / total_calls * 100, 2) if total_calls > 0 else 0,
            'avg_duration_seconds': round(avg_duration, 2),
            'inbound_calls': inbound,
            'outbound_calls': outbound
        })
    
    @action(detail=False, methods=['post'], url_path='call-logs/(?P<log_id>[0-9]+)/add-note')
    def add_note_to_call(self, request, log_id=None):
        """
        Add a note to a call log
        """
        try:
            log = CallLog.objects.get(id=log_id)
            note = request.data.get('note', '')
            
            if note:
                if log.notes:
                    log.notes += f"\n---\n{note}"
                else:
                    log.notes = note
                log.save()
                
                return Response({
                    'status': 'note added',
                    'notes': log.notes
                })
            else:
                return Response({'error': 'note is required'}, status=400)
                
        except CallLog.DoesNotExist:
            return Response({'error': 'Call log not found'}, status=404)
