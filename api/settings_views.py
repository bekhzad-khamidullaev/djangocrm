"""
ViewSets for System Settings API endpoints
"""
from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from settings.models import MassmailSettings, PublicEmailDomain, Reminders


@extend_schema(tags=['System Settings'])
class SystemSettingsViewSet(viewsets.ViewSet):
    """
    API endpoints for system settings management
    Requires admin permissions
    """
    permission_classes = [permissions.IsAdminUser]
    
    @action(detail=False, methods=['get', 'patch'])
    def massmail(self, request):
        """Get or update massmail settings"""
        settings_obj, _ = MassmailSettings.objects.get_or_create(pk=1)
        
        if request.method == 'GET':
            return Response({
                'emails_per_day': settings_obj.emails_per_day,
                'use_business_time': settings_obj.use_business_time,
                'business_time_start': settings_obj.business_time_start.strftime('%H:%M') if settings_obj.business_time_start else None,
                'business_time_end': settings_obj.business_time_end.strftime('%H:%M') if settings_obj.business_time_end else None,
                'unsubscribe_url': settings_obj.unsubscribe_url,
            })
        
        elif request.method == 'PATCH':
            # Update fields
            if 'emails_per_day' in request.data:
                settings_obj.emails_per_day = request.data['emails_per_day']
            if 'use_business_time' in request.data:
                settings_obj.use_business_time = request.data['use_business_time']
            if 'business_time_start' in request.data:
                settings_obj.business_time_start = request.data['business_time_start']
            if 'business_time_end' in request.data:
                settings_obj.business_time_end = request.data['business_time_end']
            if 'unsubscribe_url' in request.data:
                settings_obj.unsubscribe_url = request.data['unsubscribe_url']
            
            settings_obj.save()
            return Response({'status': 'updated'})
    
    @action(detail=False, methods=['get', 'patch'])
    def reminders(self, request):
        """Get or update reminder settings"""
        settings_obj, _ = Reminders.objects.get_or_create(pk=1)
        
        if request.method == 'GET':
            return Response({
                'check_interval': settings_obj.check_interval,
            })
        
        elif request.method == 'PATCH':
            if 'check_interval' in request.data:
                settings_obj.check_interval = request.data['check_interval']
                settings_obj.save()
            return Response({'status': 'updated'})
    
    @action(detail=False, methods=['get'])
    def public_email_domains(self, request):
        """Get list of public email domains"""
        domains = PublicEmailDomain.objects.all().values_list('domain', flat=True)
        return Response({'domains': list(domains)})
