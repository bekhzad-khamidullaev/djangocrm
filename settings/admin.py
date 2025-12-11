from django.contrib import admin
from django.http import HttpResponseRedirect
from django.utils.html import format_html

from crm.site.crmadminsite import crm_site
from settings.models import (
    BannedCompanyName,
    MassmailSettings,
    PublicEmailDomain,
    Reminders,
    StopPhrase,
    SystemSettings,
    APIKey,
    Webhook,
    WebhookDelivery,
    IntegrationLog,
    NotificationSettings,
    SecuritySettings,
)


class BannedCompanyNameAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


class MassmailSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "emails_per_day",
                    "use_business_time",
                    "business_time_start",
                    "business_time_end",
                    "unsubscribe_url",
                )
            },
        ),
    )

    # -- ModelAdmin methods -- #

    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(request.path + "1/change/")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PublicEmailDomainAdmin(admin.ModelAdmin):
    list_display = ('domain',)
    search_fields = ('domain',)


class RemindersAdmin(admin.ModelAdmin):

    # -- ModelAdmin methods -- #

    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(request.path + "1/change/")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class StopPhraseAdmin(admin.ModelAdmin):
    actions = ['delete_selected']
    list_display = ('phrase', 'last_occurrence_date')
    search_fields = ('phrase',)


class SystemSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            "Company Information",
            {
                "fields": (
                    "company_name",
                    "company_email",
                    "company_phone",
                )
            },
        ),
        (
            "Regional Settings",
            {
                "fields": (
                    "default_language",
                    "timezone",
                )
            },
        ),
    )
    
    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(request.path + "1/change/")
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('name', 'key_preview_display', 'user', 'is_active', 'created_at', 'last_used', 'usage_count')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'user__username', 'user__email')
    readonly_fields = ('id', 'key_preview', 'key_hash', 'created_at', 'last_used', 'usage_count')
    date_hierarchy = 'created_at'
    
    fieldsets = (
        (None, {
            'fields': ('name', 'user', 'is_active')
        }),
        ('Key Information', {
            'fields': ('key_preview', 'key_hash', 'permissions'),
            'classes': ('collapse',)
        }),
        ('Usage Statistics', {
            'fields': ('usage_count', 'last_used', 'created_at'),
        }),
    )
    
    def key_preview_display(self, obj):
        return obj.key_preview
    key_preview_display.short_description = 'API Key'
    
    def has_add_permission(self, request):
        # API keys should be created via API only
        return False


class WebhookDeliveryInline(admin.TabularInline):
    model = WebhookDelivery
    extra = 0
    readonly_fields = ('event', 'status', 'status_code', 'duration_ms', 'retry_count', 'created_at')
    can_delete = False
    max_num = 10
    
    def has_add_permission(self, request, obj=None):
        return False


class WebhookAdmin(admin.ModelAdmin):
    list_display = ('url', 'is_active', 'created_at', 'last_triggered', 'success_count', 'failure_count')
    list_filter = ('is_active', 'created_at')
    search_fields = ('url',)
    readonly_fields = ('id', 'created_at', 'last_triggered', 'success_count', 'failure_count')
    date_hierarchy = 'created_at'
    inlines = [WebhookDeliveryInline]
    
    fieldsets = (
        (None, {
            'fields': ('url', 'events', 'is_active')
        }),
        ('Security', {
            'fields': ('secret',),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('success_count', 'failure_count', 'last_triggered', 'created_at'),
        }),
    )


class IntegrationLogAdmin(admin.ModelAdmin):
    list_display = ('integration', 'action', 'status', 'timestamp', 'duration_ms', 'user')
    list_filter = ('integration', 'status', 'timestamp')
    search_fields = ('integration', 'action', 'error_message')
    readonly_fields = ('id', 'integration', 'action', 'status', 'timestamp', 'request_data', 
                      'response_data', 'error_message', 'duration_ms', 'user', 'stack_trace', 'metadata')
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'notify_new_leads', 'notify_missed_calls', 'email_digest_frequency')
    list_filter = ('email_digest_frequency', 'notify_new_leads', 'notify_missed_calls')
    search_fields = ('user__username', 'user__email')
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Event Notifications', {
            'fields': (
                'notify_new_leads',
                'notify_missed_calls',
                'notify_task_assigned',
                'notify_deal_won',
                'notify_message_received',
                'push_notifications',
            )
        }),
        ('Email Settings', {
            'fields': ('email_digest_frequency',)
        }),
        ('Quiet Hours', {
            'fields': ('quiet_hours_start', 'quiet_hours_end'),
            'classes': ('collapse',)
        }),
        ('Channels', {
            'fields': (
                'channel_email',
                'channel_sms',
                'channel_push',
                'channel_telegram',
                'channel_in_app',
            ),
            'classes': ('collapse',)
        }),
    )


class SecuritySettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Access Control', {
            'fields': ('ip_whitelist', 'rate_limit', 'require_2fa', 'session_timeout')
        }),
        ('Password Policy', {
            'fields': (
                'password_min_length',
                'password_require_uppercase',
                'password_require_lowercase',
                'password_require_numbers',
                'password_require_special',
                'password_expiry_days',
            )
        }),
        ('Login Security', {
            'fields': ('login_attempts_limit', 'lockout_duration')
        }),
    )
    
    def changelist_view(self, request, extra_context=None):
        return HttpResponseRedirect(request.path + "1/change/")
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# Register with CRM site
crm_site.register(BannedCompanyName, BannedCompanyNameAdmin)
crm_site.register(PublicEmailDomain, PublicEmailDomainAdmin)
crm_site.register(StopPhrase, StopPhraseAdmin)

# Register with default admin site
admin.site.register(BannedCompanyName, BannedCompanyNameAdmin)
admin.site.register(MassmailSettings, MassmailSettingsAdmin)
admin.site.register(PublicEmailDomain, PublicEmailDomainAdmin)
admin.site.register(Reminders, RemindersAdmin)
admin.site.register(StopPhrase, StopPhraseAdmin)
admin.site.register(SystemSettings, SystemSettingsAdmin)
admin.site.register(APIKey, APIKeyAdmin)
admin.site.register(Webhook, WebhookAdmin)
admin.site.register(IntegrationLog, IntegrationLogAdmin)
admin.site.register(NotificationSettings, NotificationSettingsAdmin)
admin.site.register(SecuritySettings, SecuritySettingsAdmin)
