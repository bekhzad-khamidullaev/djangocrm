from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from crm.utils.admfilters import ScrollRelatedOnlyFieldListFilter

from voip.models import Connection
from voip.models import IncomingCall
from voip.models import VoipSettings, OnlinePBXSettings, ZadarmaSettings, AsteriskInternalSettings, AsteriskExternalSettings
from voip.models import SipServer, InternalNumber, SipAccount, AsteriskInternalSettings, AsteriskExternalSettings
from voip.models import NumberGroup, CallRoutingRule, CallQueue, CallLog
from voip.models import PsEndpoint, PsAuth, PsAor, PsContact, PsIdentify, PsTransport, Extension
from voip.admin_views import get_voip_admin_urls
from django.utils.html import format_html
from django.contrib import messages


class ConnectionAdmin(admin.ModelAdmin):
    list_display = (
        'callerid', 'provider', 'number', 'type', 'owner', 'active'
    )
    list_filter = (
        'active', 'type',
        ('owner', ScrollRelatedOnlyFieldListFilter)
    )
    fieldsets = (
        (None, {
            'fields': (
                ('provider', 'active'),
                ('number', 'type'),
                'callerid', 'owner'
            )
        }),
    )


admin.site.register(Connection, ConnectionAdmin)


@admin.register(IncomingCall)
class IncomingCallAdmin(admin.ModelAdmin):
    list_display = (
        'caller_id', 'client_name', 'client_type',
        'user', 'created_at', 'is_consumed'
    )
    list_filter = ('is_consumed', 'client_type')
    search_fields = ('caller_id', 'client_name', 'user__username')


class ZadarmaSettingsForm(forms.ModelForm):
    class Meta:
        model = ZadarmaSettings
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        key = cleaned.get('key')
        secret = cleaned.get('secret')
        if bool(key) ^ bool(secret):
            raise forms.ValidationError(_('Both key and secret must be set for Zadarma'))
        return cleaned


@admin.register(ZadarmaSettings)
class ZadarmaSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (_("Zadarma"), {
            'fields': (
                'key', 'secret', 'allowed_ip', 'webhook_forward_ip'
            )
        }),
    )


class VoipSettingsForm(forms.ModelForm):
    ami_secret = forms.CharField(
        label='AMI secret',
        required=False,
        widget=forms.PasswordInput(render_value=True)
    )

    class Meta:
        model = VoipSettings
        fields = '__all__'


@admin.register(VoipSettings)
class VoipSettingsAdmin(admin.ModelAdmin):
    form = VoipSettingsForm
    fieldsets = (
        (_("Asterisk AMI"), {
            'fields': (
                ('ami_host', 'ami_port'),
                ('ami_username', 'ami_secret'),
                ('ami_use_ssl',),
                ('ami_connect_timeout', 'ami_reconnect_delay'),
            )
        }),
        (_("Incoming popup"), {
            'fields': (
                'incoming_enabled',
                ('incoming_poll_interval_ms', 'incoming_popup_ttl_ms'),
            )
        }),
        (_("Forwarding"), {
            'fields': (
                'forward_unknown_calls',
                'forward_url',
                'forwarding_allowed_ip',
            )
        }),
    )

    def has_add_permission(self, request):
        return not VoipSettings.objects.exists()


class OnlinePBXSettingsForm(forms.ModelForm):
    class Meta:
        model = OnlinePBXSettings
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        key_id = cleaned.get('key_id') or ''
        key = cleaned.get('key') or ''
        api_key = cleaned.get('api_key') or ''
        if not api_key and not (key_id and key):
            raise forms.ValidationError(_('Provide either API key or key_id + key'))
        return cleaned


class OnlinePBXSettingsAdmin(admin.ModelAdmin):
    form = OnlinePBXSettingsForm
    change_form_template = 'admin/voip/onlinepbxsettings/change_form_object_tools.html'
    fieldsets = (
        (_("OnlinePBX"), {
            'fields': (
                'domain',
                ('key_id', 'key'),
                'api_key',
                'base_url',
                'use_md5_base64',
            )
        }),
        (_("Webhook security"), {
            'fields': (
                'allowed_ip', 'webhook_token'
            )
        }),
    )

    def has_add_permission(self, request):
        return not OnlinePBXSettings.objects.exists()

    # Custom admin URLs for OnlinePBX operations
    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom = [
            path('user/add/', self.admin_site.admin_view(self.user_add_view), name='onlinepbx_user_add'),
            path('user/edit/', self.admin_site.admin_view(self.user_edit_view), name='onlinepbx_user_edit'),
            path('user/get/', self.admin_site.admin_view(self.user_get_view), name='onlinepbx_user_get'),
            path('user/flush-sip/', self.admin_site.admin_view(self.user_flush_sip_view), name='onlinepbx_user_flush_sip'),

            path('group/add/', self.admin_site.admin_view(self.group_add_view), name='onlinepbx_group_add'),
            path('group/edit/', self.admin_site.admin_view(self.group_edit_view), name='onlinepbx_group_edit'),
            path('group/get/', self.admin_site.admin_view(self.group_get_view), name='onlinepbx_group_get'),
            path('group/remove/', self.admin_site.admin_view(self.group_remove_view), name='onlinepbx_group_remove'),

            path('fifo/add/', self.admin_site.admin_view(self.fifo_add_view), name='onlinepbx_fifo_add'),
            path('fifo/edit/', self.admin_site.admin_view(self.fifo_edit_view), name='onlinepbx_fifo_edit'),
            path('fifo/get/', self.admin_site.admin_view(self.fifo_get_view), name='onlinepbx_fifo_get'),

            path('ivr/', self.admin_site.admin_view(self.ivr_get_view), name='onlinepbx_ivr_get'),
            path('ivr/create/', self.admin_site.admin_view(self.ivr_create_view), name='onlinepbx_ivr_create'),
            path('ivr/update/', self.admin_site.admin_view(self.ivr_update_view), name='onlinepbx_ivr_update'),
            path('ivr/delete/', self.admin_site.admin_view(self.ivr_delete_view), name='onlinepbx_ivr_delete'),

            path('blocklist/', self.admin_site.admin_view(self.blocklist_get_view), name='onlinepbx_blocklist_get'),
            path('blocklist/add/', self.admin_site.admin_view(self.blocklist_add_view), name='onlinepbx_blocklist_add'),
            path('blocklist/remove/', self.admin_site.admin_view(self.blocklist_remove_view), name='onlinepbx_blocklist_remove'),
        ]
        return custom + urls

    # Shared handler
    def _handle_form(self, request, title: str, func):
        from django.shortcuts import render
        from voip.forms.onlinepbx_admin import OnlinePBXJSONForm
        from voip.models import OnlinePBXSettings
        from voip.backends.onlinepbxbackend import OnlinePBXAPI
        import json as _json

        form = OnlinePBXJSONForm(request.POST or None)
        response_data = None
        error = None
        if request.method == 'POST' and form.is_valid():
            cfg = OnlinePBXSettings.get_solo()
            client = OnlinePBXAPI(
                domain=cfg.domain,
                key_id=cfg.key_id or None,
                key=cfg.key or None,
                api_key=cfg.api_key or None,
                base_url=cfg.base_url,
                use_base64_md5=cfg.use_md5_base64,
            )
            payload = form.cleaned_data['payload'] or ''
            use_json = form.cleaned_data['use_json']
            try:
                if use_json:
                    data = _json.loads(payload) if payload else {}
                    response_data = func(client, json_data=data)
                else:
                    # parse form-like a=b&c=d into dict
                    form_dict = {}
                    if payload:
                        for part in payload.split('&'):
                            if not part:
                                continue
                            if '=' in part:
                                k, v = part.split('=', 1)
                                form_dict[k] = v
                            else:
                                form_dict[part] = ''
                    response_data = func(client, form=form_dict)
            except Exception as exc:
                error = str(exc)
        ctx = {
            'title': title,
            'form': form,
            'result': response_data,
            'error': error,
        }
        return render(request, 'admin/voip/onlinepbxsettings/action_form.html', ctx)

    # Views mapping to client methods
    def user_add_view(self, request):
        return self._handle_form(request, _('User add'), lambda c, **kw: c.user_add(**(kw.get('json_data') or kw.get('form') or {})))

    def user_edit_view(self, request):
        return self._handle_form(request, _('User edit'), lambda c, **kw: c.user_edit(**(kw.get('json_data') or kw.get('form') or {})))

    def user_get_view(self, request):
        return self._handle_form(request, _('User get'), lambda c, **kw: c.user_get(**(kw.get('json_data') or kw.get('form') or {})))

    def user_flush_sip_view(self, request):
        return self._handle_form(request, _('User flush SIP'), lambda c, **kw: c.user_flush_sip(**(kw.get('json_data') or kw.get('form') or {})))

    def group_add_view(self, request):
        return self._handle_form(request, _('Group add'), lambda c, **kw: c.group_add(**(kw.get('json_data') or kw.get('form') or {})))

    def group_edit_view(self, request):
        return self._handle_form(request, _('Group edit'), lambda c, **kw: c.group_edit(**(kw.get('json_data') or kw.get('form') or {})))

    def group_get_view(self, request):
        return self._handle_form(request, _('Group get'), lambda c, **kw: c.group_get(**(kw.get('json_data') or kw.get('form') or {})))

    def group_remove_view(self, request):
        return self._handle_form(request, _('Group remove'), lambda c, **kw: c.group_remove(**(kw.get('json_data') or kw.get('form') or {})))

    def fifo_add_view(self, request):
        return self._handle_form(request, _('FIFO add'), lambda c, **kw: c.fifo_add(**(kw.get('json_data') or kw.get('form') or {})))

    def fifo_edit_view(self, request):
        return self._handle_form(request, _('FIFO edit'), lambda c, **kw: c.fifo_edit(**(kw.get('json_data') or kw.get('form') or {})))

    def fifo_get_view(self, request):
        return self._handle_form(request, _('FIFO get'), lambda c, **kw: c.fifo_get(**(kw.get('json_data') or kw.get('form') or {})))

    def ivr_get_view(self, request):
        return self._handle_form(request, _('IVR get'), lambda c, **kw: c.ivr_get(**(kw.get('json_data') or kw.get('form') or {})))

    def ivr_create_view(self, request):
        return self._handle_form(request, _('IVR create'), lambda c, **kw: c.ivr_create(**(kw.get('json_data') or kw.get('form') or {})))

    def ivr_update_view(self, request):
        return self._handle_form(request, _('IVR update'), lambda c, **kw: c.ivr_update(**(kw.get('json_data') or kw.get('form') or {})))

    def ivr_delete_view(self, request):
        return self._handle_form(request, _('IVR delete'), lambda c, **kw: c.ivr_delete(**(kw.get('json_data') or kw.get('form') or {})))

    def blocklist_get_view(self, request):
        return self._handle_form(request, _('Blocklist get'), lambda c, **kw: c.blocklist_get(**(kw.get('json_data') or kw.get('form') or {})))

    def blocklist_add_view(self, request):
        return self._handle_form(request, _('Blocklist add'), lambda c, **kw: c.blocklist_add_contacts(**(kw.get('json_data') or kw.get('form') or {})))

    def blocklist_remove_view(self, request):
        return self._handle_form(request, _('Blocklist remove'), lambda c, **kw: c.blocklist_remove_contacts(**(kw.get('json_data') or kw.get('form') or {})))


# SIP Management Admin Classes

@admin.register(SipServer)
class SipServerAdmin(admin.ModelAdmin):
    list_display = ('name', 'host', 'websocket_uri', 'active', 'internal_numbers_count', 'created_at')
    list_filter = ('active', 'created_at')
    search_fields = ('name', 'host', 'websocket_uri')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'host', 'active')
        }),
        (_('Connection Settings'), {
            'fields': ('websocket_uri', 'realm', 'proxy', 'register_expires')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def internal_numbers_count(self, obj):
        count = obj.internal_numbers.count()
        if count > 0:
            from django.urls import reverse
            from django.utils.html import format_html
            url = reverse('admin:voip_internalnumber_changelist')
            return format_html('<a href="{}?server__id__exact={}">{} номеров</a>', url, obj.pk, count)
        return '0 номеров'
    internal_numbers_count.short_description = _('Internal Numbers')


@admin.register(InternalNumber)
class InternalNumberAdmin(admin.ModelAdmin):
    list_display = ('number', 'server', 'user', 'display_name', 'active', 'auto_generated', 'sip_uri_display')
    list_filter = (
        'active', 'auto_generated', 'server',
        ('user', ScrollRelatedOnlyFieldListFilter)
    )
    search_fields = ('number', 'user__first_name', 'user__last_name', 'user__username', 'display_name')
    readonly_fields = ('created_at', 'updated_at', 'sip_uri')
    
    fieldsets = (
        (_('Number Configuration'), {
            'fields': ('server', 'number', 'password', 'active')
        }),
        (_('User Assignment'), {
            'fields': ('user', 'display_name', 'auto_generated')
        }),
        (_('SIP Information'), {
            'fields': ('sip_uri',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def sip_uri_display(self, obj):
        return obj.sip_uri
    sip_uri_display.short_description = _('SIP URI')
    
    actions = ['generate_passwords', 'activate_numbers', 'deactivate_numbers']
    
    def generate_passwords(self, request, queryset):
        import secrets
        import string
        
        updated = 0
        for number in queryset:
            alphabet = string.ascii_letters + string.digits
            password = ''.join(secrets.choice(alphabet) for i in range(12))
            number.password = password
            number.save()
            updated += 1
        
        self.message_user(request, f'Пароли сгенерированы для {updated} номеров.')
    generate_passwords.short_description = _('Generate new passwords')
    
    def activate_numbers(self, request, queryset):
        updated = queryset.update(active=True)
        self.message_user(request, f'{updated} номеров активировано.')
    activate_numbers.short_description = _('Activate selected numbers')
    
    def deactivate_numbers(self, request, queryset):
        updated = queryset.update(active=False)
        self.message_user(request, f'{updated} номеров деактивировано.')
    deactivate_numbers.short_description = _('Deactivate selected numbers')


@admin.register(SipAccount)
class SipAccountAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'internal_number_display', 'external_caller_id', 
        'can_make_external_calls', 'can_receive_external_calls', 
        'active', 'created_at'
    )
    list_filter = (
        'active', 'can_make_external_calls', 'can_receive_external_calls',
        'call_recording_enabled', 'voicemail_enabled',
        ('user', ScrollRelatedOnlyFieldListFilter),
        'internal_number__server'
    )
    search_fields = (
        'user__first_name', 'user__last_name', 'user__username',
        'internal_number__number', 'external_caller_id'
    )
    readonly_fields = ('created_at', 'updated_at', 'sip_config_display')
    
    fieldsets = (
        (_('Account Information'), {
            'fields': ('user', 'internal_number', 'active')
        }),
        (_('Call Permissions'), {
            'fields': (
                'can_make_external_calls', 'can_receive_external_calls',
                'external_caller_id', 'max_concurrent_calls'
            )
        }),
        (_('Features'), {
            'fields': (
                'call_recording_enabled', 'voicemail_enabled', 
                'voicemail_email'
            )
        }),
        (_('SIP Configuration'), {
            'fields': ('sip_config_display',),
            'classes': ('collapse',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def internal_number_display(self, obj):
        return f"{obj.internal_number.number}@{obj.internal_number.server.host}"
    internal_number_display.short_description = _('Internal Number')
    
    def sip_config_display(self, obj):
        from django.utils.html import format_html
        config = obj.get_jssip_config()
        html = '<table style="width:100%">'
        for key, value in config.items():
            if key == 'sip_password':
                value = '***HIDDEN***'
            html += f'<tr><td><strong>{key}:</strong></td><td>{value}</td></tr>'
        html += '</table>'
        return format_html(html)
    sip_config_display.short_description = _('JsSIP Configuration')
    
    actions = ['reset_sip_passwords']
    
    def reset_sip_passwords(self, request, queryset):
        import secrets
        import string
        
        updated = 0
        for account in queryset:
            alphabet = string.ascii_letters + string.digits
            new_password = ''.join(secrets.choice(alphabet) for i in range(12))
            account.internal_number.password = new_password
            account.internal_number.save()
            updated += 1
        
        self.message_user(request, f'Пароли сброшены для {updated} аккаунтов.')
    reset_sip_passwords.short_description = _('Reset SIP passwords')


# Call Routing and Queue Management Admin Classes

class NumberGroupMembersInline(admin.TabularInline):
    model = NumberGroup.members.through
    extra = 0
    verbose_name = _("Group Member")
    verbose_name_plural = _("Group Members")


@admin.register(NumberGroup)
class NumberGroupAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'server', 'members_count', 'distribution_strategy', 
        'ring_timeout', 'max_queue_size', 'active', 'created_at'
    )
    list_filter = ('active', 'distribution_strategy', 'server', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('members',)
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'description', 'server', 'active')
        }),
        (_('Group Members'), {
            'fields': ('members',)
        }),
        (_('Call Distribution'), {
            'fields': (
                'distribution_strategy', 'ring_timeout', 
                'max_queue_size', 'queue_timeout'
            )
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def members_count(self, obj):
        count = obj.members.count()
        available = obj.get_available_members().count()
        return f"{available}/{count} available"
    members_count.short_description = _('Members')
    
    actions = ['test_distribution', 'clear_queue']
    
    def test_distribution(self, request, queryset):
        """Тестировать распределение звонков в группах"""
        results = []
        for group in queryset:
            next_member = group.get_next_member()
            if next_member:
                results.append(f"{group.name}: следующий -> {next_member.number}")
            else:
                results.append(f"{group.name}: нет доступных членов")
        
        self.message_user(request, '; '.join(results))
    test_distribution.short_description = _('Test call distribution')
    
    def clear_queue(self, request, queryset):
        """Очистить очереди групп"""
        cleared = 0
        for group in queryset:
            if hasattr(group, 'call_queue'):
                group.call_queue.delete()
                cleared += 1
        
        self.message_user(request, f'Очищено очередей: {cleared}')
    clear_queue.short_description = _('Clear group queues')


@admin.register(CallRoutingRule)
class CallRoutingRuleAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'priority', 'action', 'target_display', 
        'active', 'created_at'
    )
    list_filter = ('active', 'action', 'created_at')
    search_fields = ('name', 'description', 'caller_id_pattern', 'called_number_pattern')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (_('Rule Information'), {
            'fields': ('name', 'description', 'priority', 'active')
        }),
        (_('Conditions'), {
            'fields': (
                'caller_id_pattern', 'called_number_pattern', 'time_condition'
            ),
            'description': _('Leave empty to match all calls')
        }),
        (_('Action'), {
            'fields': ('action',)
        }),
        (_('Action Parameters'), {
            'fields': (
                'target_number', 'target_group', 'target_external', 
                'announcement_text'
            ),
            'description': _('Fill only relevant fields based on selected action')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def target_display(self, obj):
        if obj.action == 'route_to_number' and obj.target_number:
            return f"№ {obj.target_number.number}"
        elif obj.action == 'route_to_group' and obj.target_group:
            return f"Группа {obj.target_group.name}"
        elif obj.action == 'forward_external' and obj.target_external:
            return f"Внешний {obj.target_external}"
        elif obj.action == 'play_announcement':
            return "Объявление"
        elif obj.action == 'hangup':
            return "Сброс"
        return "Не настроено"
    target_display.short_description = _('Target')
    
    actions = ['test_routing_rules', 'duplicate_rule']
    
    def test_routing_rules(self, request, queryset):
        """Тестировать правила маршрутизации"""
        test_cases = [
            ('+79001234567', '1001'),
            ('88001234567', '2000'),
            ('+74951234567', '100'),
        ]
        
        results = []
        for caller_id, called_number in test_cases:
            for rule in queryset:
                if rule.matches_call(caller_id, called_number):
                    results.append(f"{caller_id} -> {called_number}: {rule.name}")
                    break
            else:
                results.append(f"{caller_id} -> {called_number}: no match")
        
        self.message_user(request, '; '.join(results))
    test_routing_rules.short_description = _('Test routing rules')
    
    def duplicate_rule(self, request, queryset):
        """Дублировать правила"""
        duplicated = 0
        for rule in queryset:
            rule.pk = None
            rule.name = f"Copy of {rule.name}"
            rule.priority += 10
            rule.active = False
            rule.save()
            duplicated += 1
        
        self.message_user(request, f'Дублировано правил: {duplicated}')
    duplicate_rule.short_description = _('Duplicate rules')


@admin.register(CallQueue)
class CallQueueAdmin(admin.ModelAdmin):
    list_display = (
        'group', 'caller_id', 'queue_position', 'status', 
        'wait_time_display', 'wait_start_time'
    )
    list_filter = ('status', 'group', 'wait_start_time')
    search_fields = ('caller_id', 'called_number', 'session_id')
    readonly_fields = ('wait_time_display', 'wait_start_time')
    
    fieldsets = (
        (_('Call Information'), {
            'fields': ('group', 'caller_id', 'called_number', 'session_id')
        }),
        (_('Queue Status'), {
            'fields': (
                'queue_position', 'status', 'estimated_wait_time',
                'wait_start_time', 'wait_time_display'
            )
        }),
    )
    
    def wait_time_display(self, obj):
        wait_seconds = obj.wait_time
        minutes, seconds = divmod(wait_seconds, 60)
        return f"{minutes}:{seconds:02d}"
    wait_time_display.short_description = _('Current Wait Time')
    
    actions = ['move_to_front', 'remove_from_queue']
    
    def move_to_front(self, request, queryset):
        """Переместить в начало очереди"""
        updated = 0
        for queue_entry in queryset:
            if queue_entry.status == 'waiting':
                queue_entry.queue_position = 1
                queue_entry.save()
                updated += 1
        
        self.message_user(request, f'Перемещено в начало: {updated}')
    move_to_front.short_description = _('Move to front of queue')
    
    def remove_from_queue(self, request, queryset):
        """Удалить из очереди"""
        updated = queryset.update(status='abandoned')
        self.message_user(request, f'Удалено из очереди: {updated}')
    remove_from_queue.short_description = _('Remove from queue')


@admin.register(CallLog)
class CallLogAdmin(admin.ModelAdmin):
    list_display = (
        'session_id', 'caller_id', 'called_number', 'direction',
        'status', 'duration_display', 'routed_to_display', 'start_time'
    )
    list_filter = (
        'direction', 'status', 'start_time',
        ('routed_to_number', ScrollRelatedOnlyFieldListFilter),
        ('routed_to_group', ScrollRelatedOnlyFieldListFilter),
        ('routing_rule', ScrollRelatedOnlyFieldListFilter)
    )
    search_fields = (
        'session_id', 'caller_id', 'called_number', 'notes',
        'routed_to_number__number', 'routed_to_group__name'
    )
    readonly_fields = (
        'session_id', 'call_duration', 'total_duration', 
        'created_at', 'duration_display'
    )
    date_hierarchy = 'start_time'
    
    fieldsets = (
        (_('Call Information'), {
            'fields': (
                'session_id', 'caller_id', 'called_number', 'direction'
            )
        }),
        (_('Routing'), {
            'fields': (
                'routed_to_number', 'routed_to_group', 'routing_rule'
            )
        }),
        (_('Timing'), {
            'fields': (
                'start_time', 'answer_time', 'end_time',
                'duration', 'duration_display', 'queue_wait_time'
            )
        }),
        (_('Status & Details'), {
            'fields': (
                'status', 'user_agent', 'codec', 
                'recording_file', 'notes'
            )
        }),
    )
    
    def duration_display(self, obj):
        if obj.duration:
            minutes, seconds = divmod(obj.duration, 60)
            return f"{minutes}:{seconds:02d}"
        return "N/A"
    duration_display.short_description = _('Duration')
    
    def routed_to_display(self, obj):
        if obj.routed_to_number:
            result = f"№ {obj.routed_to_number.number}"
            if obj.routed_to_group:
                result += f" (группа {obj.routed_to_group.name})"
            return result
        elif obj.routed_to_group:
            return f"Группа {obj.routed_to_group.name}"
        return "Не маршрутизирован"
    routed_to_display.short_description = _('Routed To')
    
    actions = ['export_call_logs', 'generate_statistics']
    
    def export_call_logs(self, request, queryset):
        """Экспорт логов звонков"""
        # Здесь можно реализовать экспорт в CSV/Excel
        count = queryset.count()
        self.message_user(request, f'Готово к экспорту: {count} записей')
    export_call_logs.short_description = _('Export call logs')
    
    def generate_statistics(self, request, queryset):
        """Сгенерировать статистику"""
        total = queryset.count()
        answered = queryset.filter(status='answered').count()
        missed = queryset.filter(status='no_answer').count()
        
        answer_rate = round((answered / total * 100), 1) if total > 0 else 0
        
        self.message_user(
            request,
            f'Статистика: Всего {total}, отвечено {answered} ({answer_rate}%), пропущено {missed}'
        )
    generate_statistics.short_description = _('Generate statistics')


# Регистрация дополнительных URL'ов в админке
from django.contrib.admin import AdminSite
from django.urls import path, include

# Добавляем кастомные URL'ы в админку
original_get_urls = AdminSite.get_urls

def get_urls_with_voip(self):
    urls = original_get_urls(self)
    custom_urls = get_voip_admin_urls()
    return custom_urls + urls

AdminSite.get_urls = get_urls_with_voip


# ========================================
# Asterisk Real-time Admin
# ========================================

@admin.register(PsEndpoint)
class PsEndpointAdmin(admin.ModelAdmin):
    """Admin for PJSIP Endpoints"""
    list_display = (
        'id', 'context', 'transport', 'crm_user', 
        'callerid', 'codecs_display', 'registration_status'
    )
    list_filter = ('context', 'transport', 'media_encryption')
    search_fields = ('id', 'callerid', 'crm_user__username')
    readonly_fields = ('registration_status', 'endpoint_info')
    
    fieldsets = (
        (_('Basic Configuration'), {
            'fields': (
                'id', 'crm_user', 'context', 'transport',
                'aors', 'auth', 'callerid'
            )
        }),
        (_('Codecs'), {
            'fields': ('disallow', 'allow'),
            'classes': ('collapse',)
        }),
        (_('Media & RTP'), {
            'fields': (
                'direct_media', 'direct_media_method',
                'rtp_symmetric', 'force_rport', 'rewrite_contact',
                'dtmf_mode'
            ),
            'classes': ('collapse',)
        }),
        (_('Caller ID'), {
            'fields': ('callerid_privacy', 'callerid_tag'),
            'classes': ('collapse',)
        }),
        (_('Call Limits'), {
            'fields': (
                'max_audio_streams', 'max_video_streams',
                'device_state_busy_at'
            ),
            'classes': ('collapse',)
        }),
        (_('Timers'), {
            'fields': ('timers', 'timers_min_se', 'timers_sess_expires'),
            'classes': ('collapse',)
        }),
        (_('Security'), {
            'fields': (
                'media_encryption', 'media_encryption_optimistic',
                'ice_support'
            ),
            'classes': ('collapse',)
        }),
        (_('Recording'), {
            'fields': ('record_on_feature', 'record_off_feature'),
            'classes': ('collapse',)
        }),
        (_('Voicemail & MWI'), {
            'fields': ('mailboxes', 'mwi_subscribe_replaces_unsolicited'),
            'classes': ('collapse',)
        }),
        (_('Advanced'), {
            'fields': (
                'use_ptime', 'allow_subscribe', 'sub_min_expiry',
                't38_udptl', 't38_udptl_ec', 't38_udptl_maxdatagram',
                'send_pai', 'send_rpid', 'trust_id_inbound', 'trust_id_outbound'
            ),
            'classes': ('collapse',)
        }),
        (_('Status'), {
            'fields': ('registration_status', 'endpoint_info'),
            'classes': ('wide',)
        }),
    )
    
    def codecs_display(self, obj):
        if obj.allow:
            codecs = obj.allow.split(',')
            return format_html('<span style="font-family: monospace">{}</span>', ', '.join(codecs[:3]))
        return '-'
    codecs_display.short_description = _('Codecs')
    
    def registration_status(self, obj):
        """Get registration status from Asterisk"""
        try:
            from voip.models import PsContact
            import time
            
            current_time = int(time.time())
            contacts = PsContact.objects.using('asterisk').filter(
                endpoint=obj.id,
                expiration_time__gt=current_time
            )
            
            if contacts.exists():
                contact = contacts.first()
                return format_html(
                    '<span style="color: green;">✓ Registered</span><br>'
                    '<small>{}</small>',
                    contact.uri
                )
            else:
                return format_html('<span style="color: red;">✗ Not registered</span>')
        except Exception as e:
            return format_html('<span style="color: orange;">? Unknown</span>')
    registration_status.short_description = _('Registration')
    
    def endpoint_info(self, obj):
        """Display endpoint configuration summary"""
        info = []
        info.append(f"<strong>ID:</strong> {obj.id}")
        info.append(f"<strong>Context:</strong> {obj.context}")
        info.append(f"<strong>Transport:</strong> {obj.transport}")
        if obj.crm_user:
            info.append(f"<strong>User:</strong> {obj.crm_user.get_full_name() or obj.crm_user.username}")
        info.append(f"<strong>Codecs:</strong> {obj.allow}")
        return format_html('<br>'.join(info))
    endpoint_info.short_description = _('Endpoint Info')
    
    actions = ['provision_for_user', 'reload_pjsip', 'test_registration']
    
    def provision_for_user(self, request, queryset):
        """Auto-provision endpoints for selected users"""
        count = 0
        for endpoint in queryset:
            if endpoint.crm_user:
                try:
                    from voip.utils.asterisk_realtime import auto_provision_endpoint
                    result = auto_provision_endpoint(endpoint.crm_user, endpoint.id)
                    if result['success']:
                        count += 1
                except Exception as e:
                    self.message_user(request, f'Error: {e}', level=messages.ERROR)
        
        self.message_user(request, f'Provisioned {count} endpoints')
    provision_for_user.short_description = _('Re-provision endpoints')
    
    def reload_pjsip(self, request, queryset):
        """Reload PJSIP configuration"""
        try:
            from voip.backends.asteriskbackend import AsteriskRealtimeAPI
            from django.conf import settings
            
            # Get Asterisk config from DB
            try:
                cfg = AsteriskInternalSettings.get_solo()
                api = AsteriskRealtimeAPI(**cfg.to_options())
                api._reload_pjsip()
                self.message_user(request, 'PJSIP configuration reloaded')
            except Exception as e:
                self.message_user(request, f'Asterisk not configured or error: {e}', level=messages.ERROR)
        except Exception as e:
            self.message_user(request, f'Error: {e}', level=messages.ERROR)
    reload_pjsip.short_description = _('Reload PJSIP config')
    
    def test_registration(self, request, queryset):
        """Test endpoint registration"""
        registered = 0
        unregistered = 0
        
        for endpoint in queryset:
            try:
                from voip.models import PsContact
                import time
                
                current_time = int(time.time())
                if PsContact.objects.using('asterisk').filter(
                    endpoint=endpoint.id,
                    expiration_time__gt=current_time
                ).exists():
                    registered += 1
                else:
                    unregistered += 1
            except:
                pass
        
        self.message_user(
            request,
            f'Status: {registered} registered, {unregistered} not registered'
        )
    test_registration.short_description = _('Test registration')


@admin.register(PsAuth)
class PsAuthAdmin(admin.ModelAdmin):
    """Admin for PJSIP Authentication"""
    list_display = ('id', 'username', 'auth_type', 'realm', 'password_display')
    list_filter = ('auth_type',)
    search_fields = ('id', 'username', 'realm')
    
    fieldsets = (
        (None, {
            'fields': ('id', 'auth_type', 'username', 'password', 'realm')
        }),
        (_('Advanced'), {
            'fields': ('nonce_lifetime', 'md5_cred'),
            'classes': ('collapse',)
        }),
    )
    
    def password_display(self, obj):
        return '••••••••' if obj.password else '-'
    password_display.short_description = _('Password')


@admin.register(PsAor)
class PsAorAdmin(admin.ModelAdmin):
    """Admin for PJSIP Address of Records"""
    list_display = (
        'id', 'max_contacts', 'qualify_frequency', 
        'default_expiration', 'active_contacts'
    )
    list_filter = ('max_contacts',)
    search_fields = ('id', 'mailboxes')
    
    fieldsets = (
        (_('Basic Configuration'), {
            'fields': (
                'id', 'max_contacts', 'remove_existing'
            )
        }),
        (_('Expiration'), {
            'fields': (
                'minimum_expiration', 'maximum_expiration',
                'default_expiration'
            )
        }),
        (_('Qualify'), {
            'fields': (
                'qualify_frequency', 'qualify_timeout',
                'authenticate_qualify'
            )
        }),
        (_('Advanced'), {
            'fields': ('support_path', 'outbound_proxy', 'mailboxes'),
            'classes': ('collapse',)
        }),
    )
    
    def active_contacts(self, obj):
        """Show number of active contacts"""
        try:
            from voip.models import PsContact
            import time
            
            current_time = int(time.time())
            count = PsContact.objects.using('asterisk').filter(
                endpoint=obj.id,
                expiration_time__gt=current_time
            ).count()
            
            if count > 0:
                return format_html(
                    '<span style="color: green;">{}/{}</span>',
                    count, obj.max_contacts
                )
            return format_html('<span style="color: gray;">0/{}</span>', obj.max_contacts)
        except:
            return '-'
    active_contacts.short_description = _('Active Contacts')


@admin.register(PsContact)
class PsContactAdmin(admin.ModelAdmin):
    """Admin for PJSIP Contacts (read-only)"""
    list_display = (
        'endpoint', 'uri', 'user_agent', 
        'expiration_display', 'is_expired'
    )
    list_filter = ('endpoint',)
    search_fields = ('endpoint', 'uri', 'user_agent')
    readonly_fields = (
        'id', 'endpoint', 'uri', 'expiration_time', 
        'user_agent', 'reg_server', 'path'
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return True  # Allow cleanup of expired
    
    def expiration_display(self, obj):
        """Display expiration time"""
        from datetime import datetime
        try:
            dt = datetime.fromtimestamp(obj.expiration_time)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return '-'
    expiration_display.short_description = _('Expires At')
    
    def is_expired(self, obj):
        """Check if contact is expired"""
        import time
        current_time = int(time.time())
        
        if obj.expiration_time < current_time:
            return format_html('<span style="color: red;">✗ Expired</span>')
        else:
            remaining = obj.expiration_time - current_time
            minutes = remaining // 60
            return format_html(
                '<span style="color: green;">✓ Active ({} min)</span>',
                minutes
            )
    is_expired.short_description = _('Status')
    
    actions = ['cleanup_expired']
    
    def cleanup_expired(self, request, queryset):
        """Remove expired contacts"""
        import time
        current_time = int(time.time())
        
        expired = queryset.filter(expiration_time__lt=current_time)
        count = expired.count()
        expired.delete()
        
        self.message_user(request, f'Removed {count} expired contacts')
    cleanup_expired.short_description = _('Remove expired contacts')


@admin.register(PsIdentify)
class PsIdentifyAdmin(admin.ModelAdmin):
    """Admin for PJSIP IP-based Identification"""
    list_display = ('id', 'endpoint', 'match', 'srv_lookups')
    list_filter = ('srv_lookups',)
    search_fields = ('id', 'endpoint', 'match')
    
    fieldsets = (
        (None, {
            'fields': ('id', 'endpoint', 'match', 'srv_lookups')
        }),
        (_('Advanced'), {
            'fields': ('match_header',),
            'classes': ('collapse',)
        }),
    )


@admin.register(PsTransport)
class PsTransportAdmin(admin.ModelAdmin):
    """Admin for PJSIP Transports"""
    list_display = ('id', 'protocol', 'bind', 'external_addresses')
    list_filter = ('protocol',)
    search_fields = ('id', 'bind')
    
    fieldsets = (
        (_('Basic Configuration'), {
            'fields': ('id', 'protocol', 'bind')
        }),
        (_('NAT Settings'), {
            'fields': (
                'external_media_address', 'external_signaling_address',
                'local_net'
            )
        }),
        (_('TLS Settings'), {
            'fields': (
                'cert_file', 'priv_key_file', 'ca_list_file',
                'verify_server', 'verify_client', 'require_client_cert',
                'method', 'cipher'
            ),
            'classes': ('collapse',)
        }),
        (_('WebSocket Settings'), {
            'fields': ('websocket_write_timeout',),
            'classes': ('collapse',)
        }),
    )
    
    def external_addresses(self, obj):
        """Display external addresses"""
        addrs = []
        if obj.external_media_address:
            addrs.append(f'Media: {obj.external_media_address}')
        if obj.external_signaling_address:
            addrs.append(f'SIP: {obj.external_signaling_address}')
        
        if addrs:
            return format_html('<br>'.join(addrs))
        return '-'
    external_addresses.short_description = _('External Addresses')


@admin.register(Extension)
class ExtensionAdmin(admin.ModelAdmin):
    """Admin for Dialplan Extensions"""
    list_display = (
        'context', 'exten', 'priority', 'app', 
        'appdata_short', 'dialplan_display'
    )
    list_filter = ('context', 'app')
    search_fields = ('exten', 'context', 'app', 'appdata')
    ordering = ('context', 'exten', 'priority')
    
    fieldsets = (
        (None, {
            'fields': ('context', 'exten', 'priority', 'app', 'appdata')
        }),
    )
    
    def appdata_short(self, obj):
        """Display truncated appdata"""
        if len(obj.appdata) > 50:
            return obj.appdata[:50] + '...'
        return obj.appdata
    appdata_short.short_description = _('Arguments')
    
    def dialplan_display(self, obj):
        """Display as dialplan syntax"""
        return format_html(
            '<code style="background: #f5f5f5; padding: 2px 5px;">'
            'exten => {},{},({}({}))</code>',
            obj.exten, obj.priority, obj.app, obj.appdata
        )
    dialplan_display.short_description = _('Dialplan Syntax')
    
    actions = ['export_dialplan', 'reload_dialplan']
    
    def export_dialplan(self, request, queryset):
        """Export as dialplan configuration"""
        # Group by context
        from collections import defaultdict
        contexts = defaultdict(list)
        
        for ext in queryset.order_by('context', 'exten', 'priority'):
            contexts[ext.context].append(ext)
        
        output = []
        for context, extensions in contexts.items():
            output.append(f'[{context}]')
            for ext in extensions:
                output.append(f'exten => {ext.exten},{ext.priority},{ext.app}({ext.appdata})')
            output.append('')
        
        # In a real implementation, this would return a file
        self.message_user(
            request,
            f'Exported {queryset.count()} extensions from {len(contexts)} contexts'
        )
    export_dialplan.short_description = _('Export as dialplan')
    
    def reload_dialplan(self, request, queryset):
        """Reload Asterisk dialplan"""
        try:
            from voip.backends.asteriskbackend import AsteriskRealtimeAPI
            try:
                cfg = AsteriskInternalSettings.get_solo()
                api = AsteriskRealtimeAPI(**cfg.to_options())
                api._reload_dialplan()
                self.message_user(request, 'Dialplan reloaded')
            except Exception as e:
                self.message_user(request, f'Asterisk not configured or error: {e}', level=messages.ERROR)
        except Exception as e:
            self.message_user(request, f'Error: {e}', level=messages.ERROR)
    reload_dialplan.short_description = _('Reload dialplan')


@admin.register(AsteriskInternalSettings)
class AsteriskInternalSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (_("AMI"), {
            'fields': (
                ('ami_host', 'ami_port'),
                ('ami_username', 'ami_secret'),
                ('ami_timeout', 'ami_reconnect'),
            )
        }),
        (_("Dialplan"), {
            'fields': (
                'default_context', 'external_context'
            )
        }),
        (_("Transport/NAT"), {
            'fields': (
                'default_transport', 'external_ip', 'local_net'
            )
        }),
        (_("Codecs/Provisioning"), {
            'fields': (
                'codecs', 'auto_provision', 'start_extension'
            )
        }),
        (_("Recording/Queues"), {
            'fields': (
                'recordings_path', 'recording_format', 'queue_strategy', 'queue_timeout'
            )
        }),
    )


@admin.register(AsteriskExternalSettings)
class AsteriskExternalSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (_("AMI"), {
            'fields': (
                ('ami_host', 'ami_port'),
                ('ami_username', 'ami_secret'),
                ('ami_timeout',),
            )
        }),
    )

