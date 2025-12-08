from django.contrib import admin
from django.db.models import Count, Q
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import AuthenticationLog


@admin.register(AuthenticationLog)
class AuthenticationLogAdmin(admin.ModelAdmin):
    list_display = [
        'timestamp',
        'username',
        'colored_auth_type',
        'success_icon',
        'endpoint',
        'method',
        'ip_address',
    ]
    list_filter = [
        'auth_type',
        'success',
        'method',
        'timestamp',
    ]
    search_fields = [
        'username',
        'endpoint',
        'ip_address',
        'user_agent',
    ]
    readonly_fields = [
        'user',
        'username',
        'auth_type',
        'endpoint',
        'method',
        'success',
        'ip_address',
        'user_agent',
        'timestamp',
    ]
    date_hierarchy = 'timestamp'
    list_per_page = 50
    
    def has_add_permission(self, request):
        """Logs are created automatically, no manual addition"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Logs are read-only"""
        return False
    
    def colored_auth_type(self, obj):
        """Display auth type with color coding"""
        colors = {
            'jwt': '#27ae60',  # Green
            'legacy': '#f39c12',  # Orange
            'session': '#3498db',  # Blue
        }
        color = colors.get(obj.auth_type, '#7f8c8d')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_auth_type_display()
        )
    colored_auth_type.short_description = _('Auth Type')
    
    def success_icon(self, obj):
        """Display success/failure icon"""
        if obj.success:
            return format_html('<span style="color: green; font-size: 16px;">✓</span>')
        else:
            return format_html('<span style="color: red; font-size: 16px;">✗</span>')
    success_icon.short_description = _('Success')
    
    def changelist_view(self, request, extra_context=None):
        """Add statistics to the changelist view"""
        extra_context = extra_context or {}
        
        # Get statistics
        queryset = self.get_queryset(request)
        
        total_count = queryset.count()
        jwt_count = queryset.filter(auth_type='jwt').count()
        legacy_count = queryset.filter(auth_type='legacy').count()
        session_count = queryset.filter(auth_type='session').count()
        
        success_count = queryset.filter(success=True).count()
        failure_count = queryset.filter(success=False).count()
        
        # Calculate percentages
        jwt_percentage = (jwt_count / total_count * 100) if total_count > 0 else 0
        legacy_percentage = (legacy_count / total_count * 100) if total_count > 0 else 0
        success_rate = (success_count / total_count * 100) if total_count > 0 else 0
        
        extra_context['auth_stats'] = {
            'total_count': total_count,
            'jwt_count': jwt_count,
            'jwt_percentage': round(jwt_percentage, 1),
            'legacy_count': legacy_count,
            'legacy_percentage': round(legacy_percentage, 1),
            'session_count': session_count,
            'success_count': success_count,
            'failure_count': failure_count,
            'success_rate': round(success_rate, 1),
        }
        
        # Top endpoints
        top_endpoints = queryset.values('endpoint', 'auth_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        extra_context['top_endpoints'] = top_endpoints
        
        # Top users
        top_users = queryset.values('username', 'auth_type').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        extra_context['top_users'] = top_users
        
        return super().changelist_view(request, extra_context=extra_context)
