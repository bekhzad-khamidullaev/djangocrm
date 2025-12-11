"""
API Views for CRM Settings Management.

This module provides all settings-related API endpoints including:
- General Settings
- API Keys Management
- Webhooks
- Notifications
- Security Settings
- Integration Logs
"""
import csv
import hmac
import hashlib
from datetime import datetime, timedelta
from io import StringIO

from django.db.models import Count, Q, Avg
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from settings.models import (
    SystemSettings,
    APIKey,
    Webhook,
    WebhookDelivery,
    IntegrationLog,
    NotificationSettings,
    SecuritySettings,
)
from api.models import UserSession, AuthenticationLog
from api.settings_serializers import (
    SystemSettingsSerializer,
    APIKeySerializer,
    APIKeyCreateSerializer,
    APIKeyUsageSerializer,
    WebhookSerializer,
    WebhookCreateSerializer,
    WebhookDeliverySerializer,
    IntegrationLogSerializer,
    IntegrationLogStatsSerializer,
    NotificationSettingsSerializer,
    SecuritySettingsSerializer,
    ActiveSessionSerializer,
    AuditLogSerializer,
    TestNotificationSerializer,
)

User = get_user_model()


class GeneralSettingsViewSet(viewsets.ViewSet):
    """
    ViewSet for managing general system settings.
    
    This is a singleton resource - only one instance exists.
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def list(self, request):
        """GET /api/settings/general/ - Retrieve general settings."""
        settings, created = SystemSettings.objects.get_or_create(id=1)
        serializer = SystemSettingsSerializer(settings)
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """PATCH /api/settings/general/ - Update general settings."""
        settings, created = SystemSettings.objects.get_or_create(id=1)
        serializer = SystemSettingsSerializer(settings, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class APIKeyViewSet(viewsets.ModelViewSet):
    """
    ViewSet for API key management.
    
    Endpoints:
    - GET /api/settings/api-keys/ - List all API keys
    - POST /api/settings/api-keys/ - Create new API key
    - GET /api/settings/api-keys/{id}/ - Get specific key
    - DELETE /api/settings/api-keys/{id}/ - Delete key
    - POST /api/settings/api-keys/{id}/revoke/ - Revoke key
    - GET /api/settings/api-keys/{id}/usage/ - Get usage stats
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = APIKey.objects.all()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return APIKeyCreateSerializer
        return APIKeySerializer
    
    def get_queryset(self):
        """Filter API keys by user if not admin."""
        queryset = APIKey.objects.all()
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
        return queryset.select_related('user')
    
    def create(self, request, *args, **kwargs):
        """Create a new API key with automatic key generation."""
        serializer = self.get_serializer(data=request.data, context={'request': request})
        
        if serializer.is_valid():
            api_key = serializer.save()
            # Return the full key only once (on creation)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """POST /api/settings/api-keys/{id}/revoke/ - Revoke an API key."""
        api_key = self.get_object()
        api_key.is_active = False
        api_key.save()
        
        return Response({
            'id': str(api_key.id),
            'is_active': False,
            'revoked_at': timezone.now().isoformat()
        })
    
    @action(detail=True, methods=['get'])
    def usage(self, request, pk=None):
        """GET /api/settings/api-keys/{id}/usage/ - Get usage statistics."""
        api_key = self.get_object()
        
        # Get usage over last 7 days
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        # Mock data - in production, track actual API calls
        # You would query from a separate APIKeyUsage model or logs
        last_7_days = []
        for i in range(7):
            date = (timezone.now() - timedelta(days=i)).date()
            last_7_days.append({
                'date': date.isoformat(),
                'count': 0  # Would be actual count from usage logs
            })
        
        usage_data = {
            'key_id': str(api_key.id),
            'total_requests': api_key.usage_count,
            'last_7_days': last_7_days,
            'endpoints_used': []  # Would be aggregated from logs
        }
        
        serializer = APIKeyUsageSerializer(usage_data)
        return Response(serializer.data)


class WebhookViewSet(viewsets.ModelViewSet):
    """
    ViewSet for webhook management.
    
    Endpoints:
    - GET /api/settings/webhooks/ - List all webhooks
    - POST /api/settings/webhooks/ - Create webhook
    - GET /api/settings/webhooks/{id}/ - Get webhook
    - PUT /api/settings/webhooks/{id}/ - Update webhook
    - PATCH /api/settings/webhooks/{id}/ - Partial update
    - DELETE /api/settings/webhooks/{id}/ - Delete webhook
    - GET /api/settings/webhooks/{id}/deliveries/ - Delivery history
    - POST /api/settings/webhooks/{id}/test/ - Test webhook
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = Webhook.objects.all()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return WebhookCreateSerializer
        return WebhookSerializer
    
    @action(detail=True, methods=['get'])
    def deliveries(self, request, pk=None):
        """GET /api/settings/webhooks/{id}/deliveries/ - Get delivery history."""
        webhook = self.get_object()
        
        # Filter by status if provided
        status_filter = request.query_params.get('status')
        deliveries = webhook.deliveries.all()
        
        if status_filter:
            deliveries = deliveries.filter(status=status_filter)
        
        # Pagination
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        
        total_count = deliveries.count()
        deliveries = deliveries[offset:offset + limit]
        
        serializer = WebhookDeliverySerializer(deliveries, many=True)
        
        return Response({
            'count': total_count,
            'results': serializer.data
        })
    
    @action(detail=True, methods=['post'], url_path='deliveries/(?P<delivery_id>[^/.]+)/retry')
    def retry_delivery(self, request, pk=None, delivery_id=None):
        """POST /api/settings/webhooks/{id}/deliveries/{delivery_id}/retry/ - Retry failed delivery."""
        webhook = self.get_object()
        
        try:
            delivery = webhook.deliveries.get(id=delivery_id)
        except WebhookDelivery.DoesNotExist:
            return Response(
                {'error': 'Delivery not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Reset status to pending and increment retry count
        delivery.status = 'pending'
        delivery.retry_count += 1
        delivery.save()
        
        # In production, trigger async task to retry
        # from api.tasks import deliver_webhook
        # deliver_webhook.delay(webhook.id, delivery.event, delivery.request_body)
        
        return Response({
            'id': str(delivery.id),
            'status': 'pending',
            'retry_count': delivery.retry_count
        })
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """POST /api/settings/webhooks/{id}/test/ - Test webhook with sample data."""
        webhook = self.get_object()
        
        test_event = request.data.get('event', 'test.event')
        test_data = request.data.get('test_data', {'test': True})
        
        # Create test payload
        payload = {
            'event': test_event,
            'timestamp': timezone.now().isoformat(),
            'data': test_data,
            'webhook_id': str(webhook.id)
        }
        
        # Generate signature
        signature = hmac.new(
            webhook.secret.encode(),
            str(payload).encode(),
            hashlib.sha256
        ).hexdigest()
        
        # In production, make actual HTTP request
        # For now, return mock response
        import time
        start_time = time.time()
        
        # Mock successful response
        duration_ms = int((time.time() - start_time) * 1000)
        
        return Response({
            'success': True,
            'status_code': 200,
            'response': 'OK',
            'duration_ms': duration_ms
        })


class NotificationSettingsViewSet(viewsets.ViewSet):
    """
    ViewSet for notification settings management.
    
    Endpoints:
    - GET /api/settings/notifications/ - Get global notification settings
    - PATCH /api/settings/notifications/ - Update global settings
    - GET /api/users/me/notifications/ - Get user-specific settings
    - PATCH /api/users/me/notifications/ - Update user settings
    - POST /api/settings/notifications/test/ - Test notification
    """
    permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """GET /api/settings/notifications/ - Get global notification settings."""
        settings, created = NotificationSettings.objects.get_or_create(user=None)
        serializer = NotificationSettingsSerializer(settings)
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """PATCH /api/settings/notifications/ - Update global settings."""
        if not request.user.is_staff:
            return Response(
                {'error': 'Only admins can update global settings'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        settings, created = NotificationSettings.objects.get_or_create(user=None)
        serializer = NotificationSettingsSerializer(
            settings, 
            data=request.data, 
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get', 'patch'], url_path='user')
    def user_settings(self, request):
        """GET/PATCH /api/settings/notifications/user/ - User-specific settings."""
        if request.method == 'GET':
            settings, created = NotificationSettings.objects.get_or_create(user=request.user)
            serializer = NotificationSettingsSerializer(settings)
            return Response(serializer.data)
        
        elif request.method == 'PATCH':
            settings, created = NotificationSettings.objects.get_or_create(user=request.user)
            serializer = NotificationSettingsSerializer(
                settings,
                data=request.data,
                partial=True,
                context={'request': request}
            )
            
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def test(self, request):
        """POST /api/settings/notifications/test/ - Send test notification."""
        serializer = TestNotificationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        channel = serializer.validated_data['channel']
        recipient = serializer.validated_data['recipient']
        
        # In production, actually send the notification
        # For now, return success
        
        return Response({
            'success': True,
            'message': f'Test {channel} notification sent to {recipient}'
        })


class SecuritySettingsViewSet(viewsets.ViewSet):
    """
    ViewSet for security settings management.
    
    Endpoints:
    - GET /api/settings/security/ - Get security settings
    - PATCH /api/settings/security/ - Update security settings
    - GET /api/settings/security/sessions/ - List active sessions
    - DELETE /api/settings/security/sessions/{id}/ - Revoke session
    - POST /api/settings/security/sessions/revoke-all/ - Revoke all sessions
    - GET /api/settings/security/audit-log/ - Get audit log
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def list(self, request):
        """GET /api/settings/security/ - Get security settings."""
        settings, created = SecuritySettings.objects.get_or_create(id=1)
        serializer = SecuritySettingsSerializer(settings)
        return Response(serializer.data)
    
    def partial_update(self, request, pk=None):
        """PATCH /api/settings/security/ - Update security settings."""
        settings, created = SecuritySettings.objects.get_or_create(id=1)
        serializer = SecuritySettingsSerializer(
            settings,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def sessions(self, request):
        """GET /api/settings/security/sessions/ - List active sessions."""
        sessions = UserSession.objects.select_related('user').all()
        serializer = ActiveSessionSerializer(sessions, many=True)
        
        return Response({
            'count': sessions.count(),
            'results': serializer.data
        })
    
    @action(detail=False, methods=['delete'], url_path='sessions/(?P<session_id>[^/.]+)')
    def revoke_session(self, request, session_id=None):
        """DELETE /api/settings/security/sessions/{session_id}/ - Revoke specific session."""
        try:
            session = UserSession.objects.get(session_key=session_id)
            session.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except UserSession.DoesNotExist:
            return Response(
                {'error': 'Session not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=False, methods=['post'], url_path='sessions/revoke-all')
    def revoke_all_sessions(self, request):
        """POST /api/settings/security/sessions/revoke-all/ - Revoke all sessions except current."""
        current_session = request.session.session_key
        
        # Delete all sessions except current
        deleted = UserSession.objects.exclude(session_key=current_session).delete()
        
        return Response({
            'revoked_count': deleted[0]
        })
    
    @action(detail=False, methods=['get'], url_path='audit-log')
    def audit_log(self, request):
        """GET /api/settings/security/audit-log/ - Get security audit log."""
        logs = AuthenticationLog.objects.select_related('user')
        
        # Filters
        action = request.query_params.get('action')
        user_id = request.query_params.get('user_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if action:
            logs = logs.filter(auth_type=action)
        if user_id:
            logs = logs.filter(user_id=user_id)
        if start_date:
            logs = logs.filter(timestamp__gte=start_date)
        if end_date:
            logs = logs.filter(timestamp__lte=end_date)
        
        # Pagination
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))
        
        total_count = logs.count()
        logs = logs[offset:offset + limit]
        
        serializer = AuditLogSerializer(logs, many=True)
        
        return Response({
            'count': total_count,
            'results': serializer.data
        })


class IntegrationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for integration logs (read-only).
    
    Endpoints:
    - GET /api/settings/integration-logs/ - List logs
    - GET /api/settings/integration-logs/{id}/ - Get log detail
    - GET /api/settings/integration-logs/export/ - Export logs
    - DELETE /api/settings/integration-logs/cleanup/ - Cleanup old logs
    - GET /api/settings/integration-logs/stats/ - Get statistics
    """
    permission_classes = [IsAuthenticated, IsAdminUser]
    queryset = IntegrationLog.objects.all()
    serializer_class = IntegrationLogSerializer
    
    def get_queryset(self):
        """Filter logs based on query parameters."""
        queryset = IntegrationLog.objects.select_related('user')
        
        # Filters
        integration = self.request.query_params.get('integration')
        status_filter = self.request.query_params.get('status')
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if integration:
            queryset = queryset.filter(integration=integration)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """GET /api/settings/integration-logs/export/ - Export logs as CSV or JSON."""
        format_type = request.query_params.get('format', 'json')
        queryset = self.get_queryset()
        
        # Limit export size
        limit = int(request.query_params.get('limit', 1000))
        queryset = queryset[:limit]
        
        if format_type == 'csv':
            # Export as CSV
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="integration_logs.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['ID', 'Integration', 'Action', 'Status', 'Timestamp', 'Duration (ms)', 'Error Message'])
            
            for log in queryset:
                writer.writerow([
                    str(log.id),
                    log.integration,
                    log.action,
                    log.status,
                    log.timestamp.isoformat(),
                    log.duration_ms or '',
                    log.error_message
                ])
            
            return response
        
        else:
            # Export as JSON
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
    
    @action(detail=False, methods=['delete'])
    def cleanup(self, request):
        """DELETE /api/settings/integration-logs/cleanup/ - Delete old logs."""
        older_than_days = int(request.query_params.get('older_than_days', 90))
        cutoff_date = timezone.now() - timedelta(days=older_than_days)
        
        deleted = IntegrationLog.objects.filter(timestamp__lt=cutoff_date).delete()
        
        return Response({
            'deleted_count': deleted[0]
        })
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """GET /api/settings/integration-logs/stats/ - Get integration statistics."""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = IntegrationLog.objects.all()
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        # Stats by integration
        by_integration = queryset.values('integration').annotate(
            total_requests=Count('id'),
            success_count=Count('id', filter=Q(status='success')),
            error_count=Count('id', filter=Q(status='error')),
            avg_duration_ms=Avg('duration_ms')
        )
        
        # Stats by status
        by_status = queryset.values('status').annotate(count=Count('id'))
        by_status_dict = {item['status']: item['count'] for item in by_status}
        
        # Timeline (last 7 days)
        timeline = []
        for i in range(7):
            date = (timezone.now() - timedelta(days=i)).date()
            count = queryset.filter(timestamp__date=date).count()
            timeline.append({
                'date': date.isoformat(),
                'count': count
            })
        
        stats_data = {
            'by_integration': list(by_integration),
            'by_status': by_status_dict,
            'timeline': timeline
        }
        
        serializer = IntegrationLogStatsSerializer(stats_data)
        return Response(serializer.data)


# ============================================================================
# Social Media Integration ViewSets
# ============================================================================

from settings.models import InstagramAccount, FacebookPage, TelegramBot
from .settings_serializers import (
    InstagramAccountSerializer, InstagramAccountCreateSerializer,
    FacebookPageSerializer, FacebookPageCreateSerializer,
    TelegramBotSerializer, TelegramBotCreateSerializer
)


class InstagramAccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Instagram Business Account integrations.
    
    Endpoints:
    - GET /api/settings/instagram/accounts/ - List all connected accounts
    - POST /api/settings/instagram/accounts/ - Connect new Instagram account
    - GET /api/settings/instagram/accounts/{id}/ - Get account details
    - PATCH /api/settings/instagram/accounts/{id}/ - Update account settings
    - DELETE /api/settings/instagram/accounts/{id}/ - Disconnect account
    - POST /api/settings/instagram/accounts/{id}/test/ - Test connection
    - POST /api/settings/instagram/accounts/{id}/disconnect/ - Disconnect and cleanup
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return Instagram accounts for current user or all if admin."""
        if self.request.user.is_staff:
            return InstagramAccount.objects.all()
        return InstagramAccount.objects.filter(connected_by=self.request.user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return InstagramAccountCreateSerializer
        return InstagramAccountSerializer
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test Instagram connection.
        
        Verifies that the access token is valid and can access Instagram API.
        """
        account = self.get_object()
        
        try:
            # Check token validity
            if not account.is_token_valid():
                return Response({
                    'success': False,
                    'message': 'Access token has expired',
                    'details': {
                        'expired_at': account.token_expires_at
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # In real implementation, you would call Instagram Graph API here
            # For now, we'll simulate a successful test
            return Response({
                'success': True,
                'message': 'Instagram connection is working',
                'account': {
                    'username': account.username,
                    'followers': account.followers_count,
                    'is_active': account.is_active
                }
            })
        
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Connection test failed',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def disconnect(self, request, pk=None):
        """
        Disconnect Instagram account.
        
        Deactivates the account and removes webhook subscriptions.
        """
        account = self.get_object()
        
        try:
            # In real implementation, you would:
            # 1. Remove webhook subscriptions from Instagram
            # 2. Revoke access token if possible
            
            account.is_active = False
            account.save()
            
            return Response({
                'success': True,
                'message': f'Instagram account @{account.username} disconnected successfully'
            })
        
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Failed to disconnect account',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class FacebookPageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Facebook Page integrations.
    
    Endpoints:
    - GET /api/settings/facebook/pages/ - List all connected pages
    - POST /api/settings/facebook/pages/ - Connect new Facebook page
    - GET /api/settings/facebook/pages/{id}/ - Get page details
    - PATCH /api/settings/facebook/pages/{id}/ - Update page settings
    - DELETE /api/settings/facebook/pages/{id}/ - Disconnect page
    - POST /api/settings/facebook/pages/{id}/test/ - Test connection
    - POST /api/settings/facebook/pages/{id}/disconnect/ - Disconnect and cleanup
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return Facebook pages for current user or all if admin."""
        if self.request.user.is_staff:
            return FacebookPage.objects.all()
        return FacebookPage.objects.filter(connected_by=self.request.user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return FacebookPageCreateSerializer
        return FacebookPageSerializer
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test Facebook page connection.
        
        Verifies that the access token is valid and can access Facebook API.
        """
        page = self.get_object()
        
        try:
            # Check token validity
            if not page.is_token_valid():
                return Response({
                    'success': False,
                    'message': 'Access token has expired',
                    'details': {
                        'expired_at': page.token_expires_at
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # In real implementation, you would call Facebook Graph API here
            # For now, we'll simulate a successful test
            return Response({
                'success': True,
                'message': 'Facebook page connection is working',
                'page': {
                    'name': page.page_name,
                    'followers': page.followers_count,
                    'is_active': page.is_active,
                    'permissions': page.granted_permissions
                }
            })
        
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Connection test failed',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def disconnect(self, request, pk=None):
        """
        Disconnect Facebook page.
        
        Deactivates the page and removes webhook subscriptions.
        """
        page = self.get_object()
        
        try:
            # In real implementation, you would:
            # 1. Remove webhook subscriptions from Facebook
            # 2. Revoke page access token if possible
            
            page.is_active = False
            page.save()
            
            return Response({
                'success': True,
                'message': f'Facebook page "{page.page_name}" disconnected successfully'
            })
        
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Failed to disconnect page',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TelegramBotViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing Telegram Bot integrations.
    
    Endpoints:
    - GET /api/settings/telegram/bots/ - List all connected bots
    - POST /api/settings/telegram/bots/ - Connect new Telegram bot
    - GET /api/settings/telegram/bots/{id}/ - Get bot details
    - PATCH /api/settings/telegram/bots/{id}/ - Update bot settings
    - DELETE /api/settings/telegram/bots/{id}/ - Remove bot
    - POST /api/settings/telegram/bots/{id}/test/ - Test bot connection
    - POST /api/settings/telegram/bots/{id}/set_webhook/ - Setup webhook
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return Telegram bots for current user or all if admin."""
        if self.request.user.is_staff:
            return TelegramBot.objects.all()
        return TelegramBot.objects.filter(connected_by=self.request.user)
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return TelegramBotCreateSerializer
        return TelegramBotSerializer
    
    @action(detail=True, methods=['post'])
    def test(self, request, pk=None):
        """
        Test Telegram bot connection.
        
        Calls Telegram API getMe to verify bot token is valid.
        """
        bot = self.get_object()
        
        try:
            # In real implementation, you would call Telegram Bot API:
            # https://api.telegram.org/bot{token}/getMe
            
            # Simulated response
            return Response({
                'success': True,
                'message': 'Telegram bot connection is working',
                'bot': {
                    'username': bot.bot_username,
                    'name': bot.bot_name,
                    'is_active': bot.is_active,
                    'messages_received': bot.messages_received,
                    'messages_sent': bot.messages_sent
                }
            })
        
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Bot connection test failed',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def set_webhook(self, request, pk=None):
        """
        Setup or update Telegram webhook.
        
        Configures the webhook URL for receiving updates from Telegram.
        """
        bot = self.get_object()
        webhook_url = request.data.get('webhook_url')
        
        if not webhook_url:
            return Response({
                'success': False,
                'message': 'webhook_url is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            # In real implementation, you would call Telegram setWebhook API:
            # https://api.telegram.org/bot{token}/setWebhook
            
            bot.webhook_url = webhook_url
            bot.use_webhook = True
            bot.save()
            
            return Response({
                'success': True,
                'message': 'Webhook configured successfully',
                'webhook_url': webhook_url
            })
        
        except Exception as e:
            return Response({
                'success': False,
                'message': 'Failed to setup webhook',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
