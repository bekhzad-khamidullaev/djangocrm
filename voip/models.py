from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


# Provider settings stored in DB and editable via Django Admin
# Use get_solo() to retrieve or create a single row for each settings model.

def _ami_default(key, fallback):
    return settings.ASTERISK_AMI.get(key, fallback) if hasattr(settings, 'ASTERISK_AMI') else fallback


def ami_host_default():
    return _ami_default('HOST', '127.0.0.1')


def ami_port_default():
    return _ami_default('PORT', 5038)


def ami_username_default():
    return _ami_default('USERNAME', '')


def ami_secret_default():
    return _ami_default('SECRET', '')


def ami_ssl_default():
    return _ami_default('USE_SSL', False)


def ami_connect_timeout_default():
    return _ami_default('CONNECT_TIMEOUT', 5)


def ami_reconnect_delay_default():
    return _ami_default('RECONNECT_DELAY', 5)


def incoming_enabled_default():
    return getattr(settings, 'VOIP_INCOMING_CALL_ENABLED', True)


def incoming_poll_default():
    return getattr(settings, 'VOIP_INCOMING_POLL_INTERVAL_MS', 4000)


def incoming_ttl_default():
    return getattr(settings, 'VOIP_INCOMING_POPUP_TTL_MS', 20000)


class Connection(models.Model):

    TYPE_CHOICES = [
        ('pbx', _('PBX extension')),
        ('sip', _('SIP connection')),
        ('voip', _('Virtual phone number')),
    ]
    PROVIDER_CHOICES = (
        ('Zadarma', 'Zadarma'),
        ('OnlinePBX', 'OnlinePBX'),
        ('Asterisk', 'Asterisk'),
    )
     
    type = models.CharField(
        max_length=4, default='pbx', blank=False,
        choices=TYPE_CHOICES,
        verbose_name=_("Type"),
    )
    active = models.BooleanField(
        default=False,
        verbose_name=_("Active"),
    )    
    number = models.CharField(
        max_length=30, null=False, blank=False,
        verbose_name=_("Number"),
    )
    callerid = models.CharField(
        max_length=30, null=False, blank=False,
        verbose_name=_("Caller ID"),
        help_text=_(
            'Specify the number to be displayed as \
            your phone number when you call'
        )
    )
    provider = models.CharField(
        max_length=100, null=False, blank=False,
        choices=PROVIDER_CHOICES,
        verbose_name=_("Provider"),
        help_text=_('Specify VoIP service provider')
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        blank=True, null=True, 
        on_delete=models.CASCADE,
        verbose_name=_("Owner"),
        related_name="%(app_label)s_%(class)s_owner_related",
    )


class VoipSettings(models.Model):
    class Meta:
        verbose_name = _("VoIP settings")
        verbose_name_plural = _("VoIP settings")

    # Asterisk AMI
    ami_host = models.CharField(
        max_length=128,
        default=ami_host_default,
        verbose_name=_("AMI host"),
    )
    ami_port = models.PositiveIntegerField(
        default=ami_port_default,
        verbose_name=_("AMI port"),
    )
    ami_username = models.CharField(
        max_length=128,
        default=ami_username_default,
        verbose_name=_("AMI username"),
    )
    ami_secret = models.CharField(
        max_length=255,
        blank=True,
        default=ami_secret_default,
        verbose_name=_("AMI secret"),
        help_text=_("Stored in plain text in DB; restrict admin access."),
    )
    ami_use_ssl = models.BooleanField(
        default=ami_ssl_default,
        verbose_name=_("AMI over SSL"),
    )
    ami_connect_timeout = models.PositiveIntegerField(
        default=ami_connect_timeout_default,
        verbose_name=_("AMI connect timeout, seconds"),
    )
    ami_reconnect_delay = models.PositiveIntegerField(
        default=ami_reconnect_delay_default,
        verbose_name=_("AMI reconnect delay, seconds"),
    )

    # Incoming call UI
    incoming_enabled = models.BooleanField(
        default=incoming_enabled_default,
        verbose_name=_("Show incoming pop-ups"),
    )
    incoming_poll_interval_ms = models.PositiveIntegerField(
        default=incoming_poll_default,
        verbose_name=_("Polling interval, ms"),
    )
    incoming_popup_ttl_ms = models.PositiveIntegerField(
        default=incoming_ttl_default,
        verbose_name=_("Popup duration, ms"),
    )

    # Forwarding settings (used when unknown caller)
    forward_unknown_calls = models.BooleanField(
        default=False,
        verbose_name=_("Forward unknown callers"),
        help_text=_("Forward webhook payload to external URL when no CRM objects are matched"),
    )
    forward_url = models.URLField(
        max_length=500,
        blank=True,
        default='',
        verbose_name=_("Forward URL"),
    )
    forwarding_allowed_ip = models.CharField(
        max_length=64,
        blank=True,
        default='',
        verbose_name=_("Allowed IP for forwarding source"),
        help_text=_("Optional: restrict forwarding source IP check (for relayed requests)"),
    )

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        # Use static string to avoid lazy proxy issues in admin log entries
        return "VoIP settings"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj:
            return obj
        return cls.objects.create()

    @property
    def ami_config(self):
        return {
            'HOST': self.ami_host,
            'PORT': self.ami_port,
            'USERNAME': self.ami_username,
            'SECRET': self.ami_secret,
            'USE_SSL': self.ami_use_ssl,
            'CONNECT_TIMEOUT': self.ami_connect_timeout,
            'RECONNECT_DELAY': self.ami_reconnect_delay,
        }

    @property
    def incoming_ui_config(self):
        return {
            'enabled': self.incoming_enabled,
            'poll_interval_ms': self.incoming_poll_interval_ms,
            'popup_ttl_ms': self.incoming_popup_ttl_ms,
        }


class ZadarmaSettings(models.Model):
    class Meta:
        verbose_name = _('Zadarma settings')
        verbose_name_plural = _('Zadarma settings')

    key = models.CharField(max_length=128, default='', blank=True, verbose_name=_('Zadarma key'))
    secret = models.CharField(max_length=255, default='', blank=True, verbose_name=_('Zadarma secret'))
    allowed_ip = models.CharField(max_length=64, default='185.45.152.42', blank=True, verbose_name=_('Allowed IP for webhooks'))
    webhook_forward_ip = models.CharField(max_length=64, default='', blank=True, verbose_name=_('Forwarding proxy IP'))
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return 'Zadarma'

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj:
            return obj
        return cls.objects.create()


class OnlinePBXSettings(models.Model):
    class Meta:
        verbose_name = _('OnlinePBX settings')
        verbose_name_plural = _('OnlinePBX settings')

    domain = models.CharField(max_length=255, verbose_name=_('OnlinePBX domain'))
    key_id = models.CharField(max_length=128, default='', blank=True, verbose_name=_('Key ID'))
    key = models.CharField(max_length=255, default='', blank=True, verbose_name=_('Secret key'))
    api_key = models.CharField(max_length=255, default='', blank=True, verbose_name=_('API key (for auth)'))
    base_url = models.CharField(max_length=255, default='https://api2.onlinepbx.ru', verbose_name=_('Base URL'))
    use_md5_base64 = models.BooleanField(default=False, verbose_name=_('Content-MD5 as base64'))
    allowed_ip = models.CharField(max_length=64, default='*', blank=True, verbose_name=_('Allowed IP for webhooks'))
    webhook_token = models.CharField(max_length=255, default='', blank=True, verbose_name=_('Webhook token'))
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.domain

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj:
            return obj
        return cls.objects.create(domain='example.onpbx.ru')


class AsteriskInternalSettings(models.Model):
    class Meta:
        verbose_name = _('Asterisk (internal) settings')
        verbose_name_plural = _('Asterisk (internal) settings')

    ami_host = models.CharField(max_length=128, default=ami_host_default, verbose_name=_('AMI host'))
    ami_port = models.PositiveIntegerField(default=ami_port_default, verbose_name=_('AMI port'))
    ami_username = models.CharField(max_length=128, default=ami_username_default, verbose_name=_('AMI username'))
    ami_secret = models.CharField(max_length=255, default=ami_secret_default, blank=True, verbose_name=_('AMI secret'))
    ami_timeout = models.PositiveIntegerField(default=ami_connect_timeout_default, verbose_name=_('AMI timeout, sec'))
    ami_reconnect = models.PositiveIntegerField(default=ami_reconnect_delay_default, verbose_name=_('AMI reconnect, sec'))

    default_context = models.CharField(max_length=128, default='from-internal', verbose_name=_('Default context'))
    external_context = models.CharField(max_length=128, default='from-pstn', verbose_name=_('External context'))

    default_transport = models.CharField(max_length=64, default='transport-udp', verbose_name=_('Default transport'))
    external_ip = models.CharField(max_length=64, default='', blank=True, verbose_name=_('External IP'))
    local_net = models.CharField(max_length=64, default='192.168.0.0/16', verbose_name=_('Local network'))

    codecs = models.CharField(max_length=255, default='ulaw,alaw,gsm,g722,opus', verbose_name=_('Codecs (comma-separated)'))
    auto_provision = models.BooleanField(default=True, verbose_name=_('Auto provision'))
    start_extension = models.PositiveIntegerField(default=1000, verbose_name=_('Start extension'))

    recordings_path = models.CharField(max_length=255, default='/var/spool/asterisk/monitor', verbose_name=_('Recordings path'))
    recording_format = models.CharField(max_length=16, default='wav', verbose_name=_('Recording format'))

    queue_strategy = models.CharField(max_length=32, default='ringall', verbose_name=_('Queue strategy'))
    queue_timeout = models.PositiveIntegerField(default=300, verbose_name=_('Queue timeout, sec'))

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return 'Asterisk (internal)'

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj:
            return obj
        return cls.objects.create()

    def to_options(self) -> dict:
        return {
            'ami_host': self.ami_host,
            'ami_port': self.ami_port,
            'ami_username': self.ami_username,
            'ami_secret': self.ami_secret,
            'ami_timeout': self.ami_timeout,
            'ami_reconnect': self.ami_reconnect,
            'default_context': self.default_context,
            'external_context': self.external_context,
            'default_transport': self.default_transport,
            'external_ip': self.external_ip,
            'local_net': self.local_net,
            'codecs': self.codecs,
            'auto_provision': self.auto_provision,
            'start_extension': self.start_extension,
            'recordings_path': self.recordings_path,
            'recording_format': self.recording_format,
            'default_queue_strategy': self.queue_strategy,
            'queue_timeout': self.queue_timeout,
        }


class AsteriskExternalSettings(models.Model):
    class Meta:
        verbose_name = _('Asterisk (external) settings')
        verbose_name_plural = _('Asterisk (external) settings')

    ami_host = models.CharField(max_length=128, default=ami_host_default, verbose_name=_('AMI host'))
    ami_port = models.PositiveIntegerField(default=ami_port_default, verbose_name=_('AMI port'))
    ami_username = models.CharField(max_length=128, default=ami_username_default, verbose_name=_('AMI username'))
    ami_secret = models.CharField(max_length=255, default=ami_secret_default, blank=True, verbose_name=_('AMI secret'))
    ami_timeout = models.PositiveIntegerField(default=ami_connect_timeout_default, verbose_name=_('AMI timeout, sec'))

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return 'Asterisk (external)'

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if obj:
            return obj
        return cls.objects.create()


class IncomingCall(models.Model):
    class Meta:
        ordering = ('-created_at',)
        verbose_name = _("Incoming call")
        verbose_name_plural = _("Incoming calls")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='voip_incoming_calls',
        verbose_name=_("User"),
    )
    caller_id = models.CharField(
        max_length=64,
        verbose_name=_("Caller ID"),
    )
    client_name = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=_("Client name"),
    )
    client_type = models.CharField(
        max_length=32,
        blank=True,
        default='',
        verbose_name=_("Object type"),
    )
    client_id = models.PositiveIntegerField(
        blank=True,
        null=True,
        verbose_name=_("Object ID"),
    )
    client_url = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name=_("Object URL"),
    )
    is_consumed = models.BooleanField(
        default=False,
        verbose_name=_("Shown to user"),
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at"),
    )
    raw_payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Payload"),
    )

    def __str__(self):
        return f"{self.caller_id} -> {self.user}"


class SipServer(models.Model):
    """SIP сервер для подключения пользователей"""
    class Meta:
        verbose_name = _("SIP Server")
        verbose_name_plural = _("SIP Servers")

    name = models.CharField(
        max_length=100,
        verbose_name=_("Server Name"),
        help_text=_("Display name for this SIP server")
    )
    host = models.CharField(
        max_length=255,
        verbose_name=_("SIP Server Host"),
        help_text=_("Domain or IP address of SIP server")
    )
    websocket_uri = models.CharField(
        max_length=255,
        verbose_name=_("WebSocket URI"),
        help_text=_("WSS URI for WebRTC connection (e.g., wss://sip.example.com:7443)")
    )
    realm = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Realm"),
        help_text=_("SIP realm, usually same as host")
    )
    proxy = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Outbound Proxy"),
        help_text=_("Optional outbound proxy server")
    )
    register_expires = models.PositiveIntegerField(
        default=600,
        verbose_name=_("Registration Expires"),
        help_text=_("Registration expiry time in seconds")
    )
    active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.host})"

    @property
    def websocket_url(self):
        """Get formatted WebSocket URL"""
        return self.websocket_uri

    @property
    def sip_domain(self):
        """Get SIP domain"""
        return self.realm or self.host


class InternalNumber(models.Model):
    """Внутренние номера для пользователей"""
    class Meta:
        verbose_name = _("Internal Number")
        verbose_name_plural = _("Internal Numbers")
        unique_together = ['server', 'number']

    server = models.ForeignKey(
        SipServer,
        on_delete=models.CASCADE,
        verbose_name=_("SIP Server"),
        related_name='internal_numbers'
    )
    number = models.CharField(
        max_length=20,
        verbose_name=_("Internal Number"),
        help_text=_("Internal extension number (e.g., 1001, 2005)")
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name='internal_number',
        null=True,
        blank=True
    )
    password = models.CharField(
        max_length=255,
        verbose_name=_("SIP Password"),
        help_text=_("SIP authentication password")
    )
    display_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Display Name"),
        help_text=_("Name to display in calls")
    )
    active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    auto_generated = models.BooleanField(
        default=False,
        verbose_name=_("Auto Generated"),
        help_text=_("Whether this number was auto-generated")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        user_info = f" ({self.user.get_full_name()})" if self.user else ""
        return f"{self.number}@{self.server.host}{user_info}"

    @property
    def sip_uri(self):
        """Get full SIP URI"""
        return f"sip:{self.number}@{self.server.sip_domain}"

    @property
    def auth_username(self):
        """Get authentication username"""
        return self.number

    def save(self, *args, **kwargs):
        # Set display name from user if not provided
        if not self.display_name and self.user:
            self.display_name = self.user.get_full_name() or self.user.username
        super().save(*args, **kwargs)

    @classmethod
    def generate_next_number(cls, server, start_from=1000):
        """Генерирует следующий доступный внутренний номер"""
        existing_numbers = set(
            cls.objects.filter(server=server)
            .values_list('number', flat=True)
        )
        
        # Преобразуем в числа и найдем максимальный
        numeric_numbers = []
        for num in existing_numbers:
            try:
                numeric_numbers.append(int(num))
            except ValueError:
                continue
        
        if numeric_numbers:
            next_number = max(numeric_numbers) + 1
        else:
            next_number = start_from
        
        # Убеждаемся что номер не занят
        while str(next_number) in existing_numbers:
            next_number += 1
            
        return str(next_number)


class SipAccount(models.Model):
    """SIP аккаунт пользователя для телефонии"""
    class Meta:
        verbose_name = _("SIP Account")
        verbose_name_plural = _("SIP Accounts")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("User"),
        related_name='sip_account'
    )
    internal_number = models.OneToOneField(
        InternalNumber,
        on_delete=models.CASCADE,
        verbose_name=_("Internal Number"),
        related_name='sip_account'
    )
    external_caller_id = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("External Caller ID"),
        help_text=_("Phone number to show for outbound calls")
    )
    can_make_external_calls = models.BooleanField(
        default=False,
        verbose_name=_("Can Make External Calls")
    )
    can_receive_external_calls = models.BooleanField(
        default=False,
        verbose_name=_("Can Receive External Calls")
    )
    call_recording_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Call Recording Enabled")
    )
    voicemail_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Voicemail Enabled")
    )
    voicemail_email = models.EmailField(
        blank=True,
        verbose_name=_("Voicemail Email"),
        help_text=_("Email to send voicemail notifications")
    )
    max_concurrent_calls = models.PositiveIntegerField(
        default=2,
        verbose_name=_("Max Concurrent Calls")
    )
    active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.internal_number.number}"

    @property
    def sip_uri(self):
        """Get SIP URI for this account"""
        return self.internal_number.sip_uri

    @property
    def websocket_uri(self):
        """Get WebSocket URI for this account"""
        return self.internal_number.server.websocket_uri

    @property
    def sip_domain(self):
        """Get SIP domain for this account"""
        return self.internal_number.server.sip_domain

    @property
    def auth_username(self):
        """Get authentication username"""
        return self.internal_number.auth_username

    @property
    def auth_password(self):
        """Get authentication password"""
        return self.internal_number.password

    @property
    def display_name(self):
        """Get display name for calls"""
        return self.internal_number.display_name

    def get_jssip_config(self):
        """Получить конфигурацию для JsSIP клиента"""
        return {
            'ws_uri': self.websocket_uri,
            'sip_uri': self.sip_uri,
            'sip_username': self.auth_username,
            'sip_password': self.auth_password,
            'display_name': self.display_name,
            'realm': self.sip_domain,
            'register_expires': self.internal_number.server.register_expires,
            'can_make_external': self.can_make_external_calls,
            'external_caller_id': self.external_caller_id,
        }


class NumberGroup(models.Model):
    """Группы внутренних номеров для маршрутизации"""
    class Meta:
        verbose_name = _("Number Group")
        verbose_name_plural = _("Number Groups")

    name = models.CharField(
        max_length=100,
        verbose_name=_("Group Name"),
        help_text=_("Display name for this group (e.g., Sales, Support, Management)")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Description of this group's purpose")
    )
    server = models.ForeignKey(
        SipServer,
        on_delete=models.CASCADE,
        verbose_name=_("SIP Server"),
        related_name='number_groups'
    )
    members = models.ManyToManyField(
        InternalNumber,
        verbose_name=_("Group Members"),
        related_name='groups',
        blank=True
    )
    distribution_strategy = models.CharField(
        max_length=20,
        choices=[
            ('round_robin', _('Round Robin')),
            ('random', _('Random')),
            ('priority', _('Priority Order')),
            ('all_ring', _('Ring All')),
            ('least_recent', _('Least Recently Called')),
        ],
        default='round_robin',
        verbose_name=_("Distribution Strategy"),
        help_text=_("How calls are distributed among group members")
    )
    ring_timeout = models.PositiveIntegerField(
        default=30,
        verbose_name=_("Ring Timeout (seconds)"),
        help_text=_("How long to ring each member before trying next")
    )
    max_queue_size = models.PositiveIntegerField(
        default=10,
        verbose_name=_("Max Queue Size"),
        help_text=_("Maximum number of callers in queue")
    )
    queue_timeout = models.PositiveIntegerField(
        default=300,
        verbose_name=_("Queue Timeout (seconds)"),
        help_text=_("Maximum time caller waits in queue")
    )
    active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.members.count()} members)"

    def get_available_members(self):
        """Получить доступных членов группы"""
        return self.members.filter(
            active=True,
            user__isnull=False,
            sip_account__active=True
        )

    def get_next_member(self, exclude_numbers=None):
        """Получить следующего члена группы по стратегии распределения"""
        available = self.get_available_members()
        
        if exclude_numbers:
            available = available.exclude(number__in=exclude_numbers)
        
        if not available.exists():
            return None

        if self.distribution_strategy == 'round_robin':
            return self._get_round_robin_member(available)
        elif self.distribution_strategy == 'random':
            return available.order_by('?').first()
        elif self.distribution_strategy == 'priority':
            return available.first()  # Предполагаем порядок по приоритету
        elif self.distribution_strategy == 'least_recent':
            return self._get_least_recent_member(available)
        else:  # all_ring
            return available

    def _get_round_robin_member(self, available):
        """Round Robin алгоритм"""
        # Простая реализация - можно улучшить с состоянием
        from datetime import datetime
        seed = int(datetime.now().timestamp()) // self.ring_timeout
        count = available.count()
        index = seed % count if count > 0 else 0
        return available[index]

    def _get_least_recent_member(self, available):
        """Выбрать того кому давно не звонили"""
        # Найти член группы с самым старым последним звонком
        from django.db.models import Max
        
        members_with_calls = available.annotate(
            last_call=Max('user__voip_incoming_calls__created_at')
        ).order_by('last_call')
        
        return members_with_calls.first()


class CallRoutingRule(models.Model):
    """Правила маршрутизации входящих звонков"""
    class Meta:
        verbose_name = _("Call Routing Rule")
        verbose_name_plural = _("Call Routing Rules")
        ordering = ['priority']

    name = models.CharField(
        max_length=100,
        verbose_name=_("Rule Name")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description")
    )
    priority = models.PositiveIntegerField(
        default=100,
        verbose_name=_("Priority"),
        help_text=_("Lower number = higher priority")
    )
    
    # Условия срабатывания
    caller_id_pattern = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Caller ID Pattern"),
        help_text=_("Regex pattern for caller ID (e.g., ^\\+7, ^8800)")
    )
    called_number_pattern = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Called Number Pattern"),
        help_text=_("Regex pattern for called number")
    )
    time_condition = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Time Condition"),
        help_text=_("Time condition (e.g., weekdays 09:00-18:00)")
    )
    
    # Действие
    action = models.CharField(
        max_length=20,
        choices=[
            ('route_to_number', _('Route to Number')),
            ('route_to_group', _('Route to Group')),
            ('route_to_queue', _('Route to Queue')),
            ('route_to_voicemail', _('Route to Voicemail')),
            ('play_announcement', _('Play Announcement')),
            ('hangup', _('Hangup')),
            ('forward_external', _('Forward to External Number')),
        ],
        verbose_name=_("Action")
    )
    
    # Параметры действия
    target_number = models.ForeignKey(
        InternalNumber,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=_("Target Number"),
        help_text=_("Target internal number for routing")
    )
    target_group = models.ForeignKey(
        NumberGroup,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name=_("Target Group"),
        help_text=_("Target group for routing")
    )
    target_external = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("External Number"),
        help_text=_("External number for forwarding")
    )
    announcement_text = models.TextField(
        blank=True,
        verbose_name=_("Announcement Text"),
        help_text=_("Text to play as announcement")
    )
    
    active = models.BooleanField(
        default=True,
        verbose_name=_("Active")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (Priority: {self.priority})"

    def matches_call(self, caller_id, called_number, call_time=None):
        """Проверить соответствует ли звонок этому правилу"""
        import re
        from datetime import datetime

        # Проверка caller ID
        if self.caller_id_pattern:
            if not re.match(self.caller_id_pattern, caller_id or ''):
                return False

        # Проверка called number
        if self.called_number_pattern:
            if not re.match(self.called_number_pattern, called_number or ''):
                return False

        # Проверка времени (упрощенная)
        if self.time_condition:
            # Здесь можно реализовать более сложную логику времени
            pass

        return True

    def execute_action(self, call_data):
        """Выполнить действие правила"""
        if self.action == 'route_to_number' and self.target_number:
            return {
                'action': 'route',
                'target_type': 'number',
                'target': self.target_number.number,
                'sip_uri': self.target_number.sip_uri
            }
        elif self.action == 'route_to_group' and self.target_group:
            next_member = self.target_group.get_next_member()
            if next_member:
                return {
                    'action': 'route',
                    'target_type': 'group_member',
                    'target': next_member.number,
                    'sip_uri': next_member.sip_uri,
                    'group': self.target_group.name
                }
            else:
                return {'action': 'busy', 'reason': 'No available group members'}
        elif self.action == 'forward_external' and self.target_external:
            return {
                'action': 'forward',
                'target_type': 'external',
                'target': self.target_external
            }
        elif self.action == 'play_announcement':
            return {
                'action': 'announcement',
                'text': self.announcement_text
            }
        elif self.action == 'hangup':
            return {'action': 'hangup'}
        
        return {'action': 'not_configured'}


class CallQueue(models.Model):
    """Очередь звонков для группы"""
    class Meta:
        verbose_name = _("Call Queue")
        verbose_name_plural = _("Call Queues")

    group = models.OneToOneField(
        NumberGroup,
        on_delete=models.CASCADE,
        verbose_name=_("Number Group"),
        related_name='call_queue'
    )
    caller_id = models.CharField(
        max_length=50,
        verbose_name=_("Caller ID")
    )
    called_number = models.CharField(
        max_length=50,
        verbose_name=_("Called Number")
    )
    queue_position = models.PositiveIntegerField(
        verbose_name=_("Queue Position")
    )
    wait_start_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Wait Start Time")
    )
    estimated_wait_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Estimated Wait Time (seconds)")
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('waiting', _('Waiting')),
            ('connecting', _('Connecting')),
            ('connected', _('Connected')),
            ('abandoned', _('Abandoned')),
            ('timeout', _('Timeout')),
        ],
        default='waiting',
        verbose_name=_("Status")
    )
    session_id = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Session ID"),
        help_text=_("SIP session identifier")
    )

    def __str__(self):
        return f"Queue {self.group.name}: {self.caller_id} (pos. {self.queue_position})"

    @property
    def wait_time(self):
        """Время ожидания в секундах"""
        from django.utils import timezone
        if self.wait_start_time:
            return int((timezone.now() - self.wait_start_time).total_seconds())
        return 0

    def update_position(self):
        """Обновить позицию в очереди"""
        higher_priority = CallQueue.objects.filter(
            group=self.group,
            wait_start_time__lt=self.wait_start_time,
            status='waiting'
        ).count()
        self.queue_position = higher_priority + 1
        self.save()


class CallLog(models.Model):
    """Детальное логирование звонков"""
    class Meta:
        verbose_name = _("Call Log")
        verbose_name_plural = _("Call Logs")
        ordering = ['-start_time']

    # Основная информация о звонке
    session_id = models.CharField(
        max_length=100,
        unique=True,
        verbose_name=_("Session ID")
    )
    caller_id = models.CharField(
        max_length=50,
        verbose_name=_("Caller ID")
    )
    called_number = models.CharField(
        max_length=50,
        verbose_name=_("Called Number")
    )
    direction = models.CharField(
        max_length=10,
        choices=[
            ('inbound', _('Inbound')),
            ('outbound', _('Outbound')),
            ('internal', _('Internal')),
        ],
        verbose_name=_("Direction")
    )
    
    # Маршрутизация
    routed_to_number = models.ForeignKey(
        InternalNumber,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Routed to Number"),
        related_name='received_calls'
    )
    routed_to_group = models.ForeignKey(
        NumberGroup,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Routed to Group"),
        related_name='group_calls'
    )
    routing_rule = models.ForeignKey(
        CallRoutingRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("Applied Routing Rule"),
        related_name='applied_calls'
    )
    
    # Временные метки
    start_time = models.DateTimeField(
        verbose_name=_("Call Start Time")
    )
    answer_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Answer Time")
    )
    end_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Call End Time")
    )
    
    # Статистика
    status = models.CharField(
        max_length=20,
        choices=[
            ('ringing', _('Ringing')),
            ('answered', _('Answered')),
            ('busy', _('Busy')),
            ('no_answer', _('No Answer')),
            ('failed', _('Failed')),
            ('abandoned', _('Abandoned')),
        ],
        default='ringing',
        verbose_name=_("Call Status")
    )
    duration = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Duration (seconds)")
    )
    queue_wait_time = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Queue Wait Time (seconds)")
    )
    
    # Дополнительная информация
    user_agent = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("User Agent")
    )
    codec = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Audio Codec")
    )
    recording_file = models.CharField(
        max_length=500,
        blank=True,
        verbose_name=_("Recording File Path")
    )
    notes = models.TextField(
        blank=True,
        verbose_name=_("Notes")
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.caller_id} -> {self.called_number} ({self.status})"

    @property
    def call_duration(self):
        """Продолжительность разговора"""
        if self.answer_time and self.end_time:
            return int((self.end_time - self.answer_time).total_seconds())
        return 0

    @property
    def total_duration(self):
        """Общая продолжительность звонка"""
        if self.end_time:
            return int((self.end_time - self.start_time).total_seconds())
        return 0

    def calculate_statistics(self):
        """Вычислить статистику звонка"""
        if self.answer_time and self.end_time:
            self.duration = self.call_duration
        elif self.end_time:
            self.duration = self.total_duration
        
        self.save()


# ========================================
# Asterisk Real-time Database Models
# ========================================

class AsteriskRealtimeBase(models.Model):
    """Base class for Asterisk Real-time models using separate database"""
    class Meta:
        abstract = True
        
    def save(self, *args, **kwargs):
        using = kwargs.pop('using', 'asterisk')
        return super().save(*args, using=using, **kwargs)
    
    def delete(self, *args, **kwargs):
        using = kwargs.pop('using', 'asterisk')
        return super().delete(*args, using=using, **kwargs)
    
    class Manager(models.Manager):
        def get_queryset(self):
            return super().get_queryset().using('asterisk')


class PsEndpoint(AsteriskRealtimeBase):
    """
    PJSIP Endpoint configuration for Asterisk Real-time
    Equivalent to pjsip.conf [endpoint] section
    """
    class Meta:
        db_table = 'ps_endpoints'
        verbose_name = _("PJSIP Endpoint")
        verbose_name_plural = _("PJSIP Endpoints")
        indexes = [
            models.Index(fields=['id']),
        ]
    
    objects = AsteriskRealtimeBase.Manager()
    
    # Primary identification
    id = models.CharField(
        max_length=40,
        primary_key=True,
        verbose_name=_("Endpoint ID"),
        help_text=_("Unique identifier for this endpoint")
    )
    
    # Transport and connection
    transport = models.CharField(
        max_length=40,
        default='transport-udp',
        verbose_name=_("Transport"),
        help_text=_("Transport to use (transport-udp, transport-tcp, transport-tls, transport-wss)")
    )
    
    # Authentication and AOR
    aors = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("AORs"),
        help_text=_("Comma-separated list of AORs (Address of Records)")
    )
    auth = models.CharField(
        max_length=40,
        blank=True,
        verbose_name=_("Authentication"),
        help_text=_("Authentication section name")
    )
    
    # Context and dialplan
    context = models.CharField(
        max_length=40,
        default='default',
        verbose_name=_("Context"),
        help_text=_("Dialplan context for incoming calls")
    )
    
    # Codecs
    disallow = models.CharField(
        max_length=200,
        default='all',
        verbose_name=_("Disallow Codecs"),
        help_text=_("Codecs to disallow")
    )
    allow = models.CharField(
        max_length=200,
        default='ulaw,alaw,gsm',
        verbose_name=_("Allow Codecs"),
        help_text=_("Codecs to allow (order matters)")
    )
    
    # Direct media / RTP
    direct_media = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Direct Media"),
        help_text=_("Enable direct media between endpoints (yes/no)")
    )
    direct_media_method = models.CharField(
        max_length=20,
        default='invite',
        blank=True,
        verbose_name=_("Direct Media Method"),
        help_text=_("Method for direct media (invite/reinvite/update)")
    )
    
    # NAT settings
    rtp_symmetric = models.CharField(
        max_length=3,
        default='yes',
        verbose_name=_("RTP Symmetric"),
        help_text=_("Send RTP to source of received RTP")
    )
    force_rport = models.CharField(
        max_length=3,
        default='yes',
        verbose_name=_("Force rport"),
        help_text=_("Force rport to be added for NAT")
    )
    rewrite_contact = models.CharField(
        max_length=3,
        default='yes',
        verbose_name=_("Rewrite Contact"),
        help_text=_("Rewrite contact header for NAT")
    )
    
    # DTMF
    dtmf_mode = models.CharField(
        max_length=10,
        default='rfc4733',
        verbose_name=_("DTMF Mode"),
        help_text=_("DTMF transmission mode (rfc4733/inband/info/auto)")
    )
    
    # Caller ID
    callerid = models.CharField(
        max_length=80,
        blank=True,
        verbose_name=_("Caller ID"),
        help_text=_('Caller ID in format "Name" <number>')
    )
    callerid_privacy = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Caller ID Privacy"),
        help_text=_("Caller ID privacy setting")
    )
    callerid_tag = models.CharField(
        max_length=40,
        blank=True,
        verbose_name=_("Caller ID Tag"),
        help_text=_("Caller ID tag")
    )
    
    # Call limits
    max_audio_streams = models.IntegerField(
        default=1,
        verbose_name=_("Max Audio Streams")
    )
    max_video_streams = models.IntegerField(
        default=0,
        verbose_name=_("Max Video Streams")
    )
    
    # Device state
    device_state_busy_at = models.IntegerField(
        default=0,
        verbose_name=_("Device State Busy At"),
        help_text=_("Number of in-use channels before device state is 'busy' (0=disabled)")
    )
    
    # Timers
    timers = models.CharField(
        max_length=3,
        default='yes',
        verbose_name=_("Session Timers"),
        help_text=_("Enable session timers")
    )
    timers_min_se = models.IntegerField(
        default=90,
        verbose_name=_("Timers Min SE"),
        help_text=_("Minimum session timer expiration (seconds)")
    )
    timers_sess_expires = models.IntegerField(
        default=1800,
        verbose_name=_("Timers Session Expires"),
        help_text=_("Session timer expiration (seconds)")
    )
    
    # Security
    media_encryption = models.CharField(
        max_length=10,
        default='no',
        verbose_name=_("Media Encryption"),
        help_text=_("Media encryption method (no/sdes/dtls)")
    )
    media_encryption_optimistic = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Media Encryption Optimistic"),
        help_text=_("Use optimistic encryption")
    )
    
    # Advanced settings
    use_ptime = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Use ptime"),
        help_text=_("Use ptime attribute in SDP")
    )
    ice_support = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("ICE Support"),
        help_text=_("Enable ICE support")
    )
    
    # Recording
    record_on_feature = models.CharField(
        max_length=40,
        blank=True,
        verbose_name=_("Record On Feature"),
        help_text=_("Feature code to start recording")
    )
    record_off_feature = models.CharField(
        max_length=40,
        blank=True,
        verbose_name=_("Record Off Feature"),
        help_text=_("Feature code to stop recording")
    )
    
    # MWI
    mailboxes = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Mailboxes"),
        help_text=_("Mailboxes for MWI (Message Waiting Indication)")
    )
    mwi_subscribe_replaces_unsolicited = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("MWI Subscribe Replaces Unsolicited")
    )
    
    # Subscription and presence
    allow_subscribe = models.CharField(
        max_length=3,
        default='yes',
        verbose_name=_("Allow Subscribe"),
        help_text=_("Allow subscriptions")
    )
    sub_min_expiry = models.IntegerField(
        default=60,
        verbose_name=_("Subscription Min Expiry")
    )
    
    # T.38 Fax
    t38_udptl = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("T.38 UDPTL"),
        help_text=_("Enable T.38 fax support")
    )
    t38_udptl_ec = models.CharField(
        max_length=20,
        default='none',
        verbose_name=_("T.38 Error Correction"),
        help_text=_("T.38 error correction method")
    )
    t38_udptl_maxdatagram = models.IntegerField(
        default=400,
        verbose_name=_("T.38 Max Datagram")
    )
    
    # Advanced codec negotiation
    codec_prefs_incoming_offer = models.CharField(
        max_length=20,
        default='prefer:pending,operation:union',
        blank=True,
        verbose_name=_("Codec Prefs Incoming Offer")
    )
    codec_prefs_outgoing_offer = models.CharField(
        max_length=20,
        default='prefer:pending,operation:intersect',
        blank=True,
        verbose_name=_("Codec Prefs Outgoing Offer")
    )
    codec_prefs_incoming_answer = models.CharField(
        max_length=20,
        default='prefer:pending,operation:intersect',
        blank=True,
        verbose_name=_("Codec Prefs Incoming Answer")
    )
    
    # Misc
    send_pai = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Send PAI"),
        help_text=_("Send P-Asserted-Identity header")
    )
    send_rpid = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Send RPID"),
        help_text=_("Send Remote-Party-ID header")
    )
    trust_id_inbound = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Trust ID Inbound")
    )
    trust_id_outbound = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Trust ID Outbound")
    )
    
    # Link to Django user (optional)
    crm_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name=_("CRM User"),
        related_name='asterisk_endpoint',
        db_constraint=False  # Cross-database, no FK constraint
    )
    
    def __str__(self):
        return f"{self.id} (context: {self.context})"


class PsAuth(AsteriskRealtimeBase):
    """
    PJSIP Authentication configuration for Asterisk Real-time
    Equivalent to pjsip.conf [auth] section
    """
    class Meta:
        db_table = 'ps_auths'
        verbose_name = _("PJSIP Auth")
        verbose_name_plural = _("PJSIP Auths")
        indexes = [
            models.Index(fields=['id']),
        ]
    
    objects = AsteriskRealtimeBase.Manager()
    
    id = models.CharField(
        max_length=40,
        primary_key=True,
        verbose_name=_("Auth ID"),
        help_text=_("Authentication identifier (usually matches endpoint)")
    )
    auth_type = models.CharField(
        max_length=10,
        default='userpass',
        verbose_name=_("Auth Type"),
        help_text=_("Authentication type (userpass/md5)")
    )
    password = models.CharField(
        max_length=80,
        verbose_name=_("Password"),
        help_text=_("Password for authentication")
    )
    username = models.CharField(
        max_length=40,
        verbose_name=_("Username"),
        help_text=_("Username for authentication")
    )
    realm = models.CharField(
        max_length=40,
        blank=True,
        verbose_name=_("Realm"),
        help_text=_("Authentication realm (optional)")
    )
    nonce_lifetime = models.IntegerField(
        default=32,
        verbose_name=_("Nonce Lifetime"),
        help_text=_("Lifetime of nonce in seconds")
    )
    md5_cred = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("MD5 Credentials"),
        help_text=_("MD5 hash credentials (for md5 auth type)")
    )
    
    def __str__(self):
        return f"{self.id} ({self.username})"


class PsAor(AsteriskRealtimeBase):
    """
    PJSIP Address of Record configuration for Asterisk Real-time
    Equivalent to pjsip.conf [aor] section
    """
    class Meta:
        db_table = 'ps_aors'
        verbose_name = _("PJSIP AOR")
        verbose_name_plural = _("PJSIP AORs")
        indexes = [
            models.Index(fields=['id']),
        ]
    
    objects = AsteriskRealtimeBase.Manager()
    
    id = models.CharField(
        max_length=40,
        primary_key=True,
        verbose_name=_("AOR ID"),
        help_text=_("Address of Record identifier")
    )
    max_contacts = models.IntegerField(
        default=1,
        verbose_name=_("Max Contacts"),
        help_text=_("Maximum number of contacts for this AOR")
    )
    remove_existing = models.CharField(
        max_length=3,
        default='yes',
        verbose_name=_("Remove Existing"),
        help_text=_("Remove existing contacts on new registration")
    )
    minimum_expiration = models.IntegerField(
        default=60,
        verbose_name=_("Minimum Expiration"),
        help_text=_("Minimum registration expiration time (seconds)")
    )
    maximum_expiration = models.IntegerField(
        default=3600,
        verbose_name=_("Maximum Expiration"),
        help_text=_("Maximum registration expiration time (seconds)")
    )
    default_expiration = models.IntegerField(
        default=3600,
        verbose_name=_("Default Expiration"),
        help_text=_("Default registration expiration time (seconds)")
    )
    qualify_frequency = models.IntegerField(
        default=0,
        verbose_name=_("Qualify Frequency"),
        help_text=_("Frequency to qualify endpoint (seconds, 0=disabled)")
    )
    qualify_timeout = models.FloatField(
        default=3.0,
        verbose_name=_("Qualify Timeout"),
        help_text=_("Timeout for qualify requests (seconds)")
    )
    authenticate_qualify = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Authenticate Qualify"),
        help_text=_("Authenticate qualify requests")
    )
    support_path = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Support Path"),
        help_text=_("Support Path header for registration")
    )
    
    # Outbound registration
    outbound_proxy = models.CharField(
        max_length=256,
        blank=True,
        verbose_name=_("Outbound Proxy"),
        help_text=_("Outbound proxy for requests")
    )
    
    # Voicemail
    mailboxes = models.CharField(
        max_length=200,
        blank=True,
        verbose_name=_("Mailboxes"),
        help_text=_("Mailboxes for this AOR")
    )
    
    def __str__(self):
        return f"{self.id} (max_contacts: {self.max_contacts})"


class PsContact(AsteriskRealtimeBase):
    """
    PJSIP Contact information (dynamic, created by registrations)
    """
    class Meta:
        db_table = 'ps_contacts'
        verbose_name = _("PJSIP Contact")
        verbose_name_plural = _("PJSIP Contacts")
        indexes = [
            models.Index(fields=['id']),
            models.Index(fields=['endpoint']),
        ]
    
    objects = AsteriskRealtimeBase.Manager()
    
    id = models.CharField(
        max_length=255,
        primary_key=True,
        verbose_name=_("Contact ID")
    )
    endpoint = models.CharField(
        max_length=40,
        verbose_name=_("Endpoint"),
        help_text=_("Associated endpoint")
    )
    uri = models.CharField(
        max_length=511,
        verbose_name=_("URI"),
        help_text=_("Contact URI")
    )
    expiration_time = models.BigIntegerField(
        verbose_name=_("Expiration Time"),
        help_text=_("Unix timestamp when registration expires")
    )
    qualify_frequency = models.IntegerField(
        default=0,
        verbose_name=_("Qualify Frequency")
    )
    qualify_timeout = models.FloatField(
        default=3.0,
        verbose_name=_("Qualify Timeout")
    )
    authenticate_qualify = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Authenticate Qualify")
    )
    outbound_proxy = models.CharField(
        max_length=256,
        blank=True,
        verbose_name=_("Outbound Proxy")
    )
    path = models.TextField(
        blank=True,
        verbose_name=_("Path"),
        help_text=_("Path header from registration")
    )
    user_agent = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("User Agent")
    )
    reg_server = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Registration Server")
    )
    
    def __str__(self):
        return f"{self.endpoint} - {self.uri}"


class PsIdentify(AsteriskRealtimeBase):
    """
    PJSIP Endpoint Identification by IP
    Equivalent to pjsip.conf [identify] section
    """
    class Meta:
        db_table = 'ps_endpoint_id_ips'
        verbose_name = _("PJSIP Identify")
        verbose_name_plural = _("PJSIP Identifies")
        indexes = [
            models.Index(fields=['id']),
            models.Index(fields=['endpoint']),
        ]
    
    objects = AsteriskRealtimeBase.Manager()
    
    id = models.CharField(
        max_length=40,
        primary_key=True,
        verbose_name=_("Identify ID")
    )
    endpoint = models.CharField(
        max_length=40,
        verbose_name=_("Endpoint"),
        help_text=_("Endpoint to associate with this identification")
    )
    match = models.CharField(
        max_length=80,
        verbose_name=_("Match"),
        help_text=_("IP address or network to match (e.g., 192.168.1.10, 192.168.1.0/24)")
    )
    srv_lookups = models.CharField(
        max_length=3,
        default='yes',
        verbose_name=_("SRV Lookups"),
        help_text=_("Enable SRV lookups")
    )
    match_header = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Match Header"),
        help_text=_("SIP header to match")
    )
    
    def __str__(self):
        return f"{self.id} - {self.match} -> {self.endpoint}"


class PsTransport(AsteriskRealtimeBase):
    """
    PJSIP Transport configuration
    Equivalent to pjsip.conf [transport] section
    """
    class Meta:
        db_table = 'ps_transports'
        verbose_name = _("PJSIP Transport")
        verbose_name_plural = _("PJSIP Transports")
        indexes = [
            models.Index(fields=['id']),
        ]
    
    objects = AsteriskRealtimeBase.Manager()
    
    id = models.CharField(
        max_length=40,
        primary_key=True,
        verbose_name=_("Transport ID")
    )
    protocol = models.CharField(
        max_length=10,
        default='udp',
        verbose_name=_("Protocol"),
        help_text=_("Transport protocol (udp/tcp/tls/ws/wss)")
    )
    bind = models.CharField(
        max_length=255,
        verbose_name=_("Bind"),
        help_text=_("IP:port to bind to (e.g., 0.0.0.0:5060)")
    )
    external_media_address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("External Media Address"),
        help_text=_("External IP for media (NAT)")
    )
    external_signaling_address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("External Signaling Address"),
        help_text=_("External IP for signaling (NAT)")
    )
    local_net = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Local Network"),
        help_text=_("Local network CIDR (e.g., 192.168.0.0/16)")
    )
    
    # TLS specific
    cert_file = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Certificate File"),
        help_text=_("Path to SSL certificate file")
    )
    priv_key_file = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Private Key File"),
        help_text=_("Path to SSL private key file")
    )
    ca_list_file = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("CA List File"),
        help_text=_("Path to CA certificate list file")
    )
    verify_server = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Verify Server"),
        help_text=_("Verify server certificate")
    )
    verify_client = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Verify Client"),
        help_text=_("Verify client certificate")
    )
    require_client_cert = models.CharField(
        max_length=3,
        default='no',
        verbose_name=_("Require Client Cert")
    )
    method = models.CharField(
        max_length=10,
        default='tlsv1_2',
        blank=True,
        verbose_name=_("SSL/TLS Method"),
        help_text=_("SSL/TLS method (sslv23/tlsv1/tlsv1_1/tlsv1_2)")
    )
    cipher = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Cipher Suite"),
        help_text=_("OpenSSL cipher suite")
    )
    
    # WebSocket specific
    websocket_write_timeout = models.IntegerField(
        default=100,
        verbose_name=_("WebSocket Write Timeout"),
        help_text=_("WebSocket write timeout in milliseconds")
    )
    
    def __str__(self):
        return f"{self.id} ({self.protocol}://{self.bind})"


class Extension(AsteriskRealtimeBase):
    """
    Asterisk Dialplan Extensions for Real-time
    """
    class Meta:
        db_table = 'extensions'
        verbose_name = _("Dialplan Extension")
        verbose_name_plural = _("Dialplan Extensions")
        ordering = ['context', 'priority']
        indexes = [
            models.Index(fields=['context', 'exten', 'priority']),
        ]
    
    objects = AsteriskRealtimeBase.Manager()
    
    id = models.AutoField(primary_key=True)
    context = models.CharField(
        max_length=40,
        verbose_name=_("Context"),
        help_text=_("Dialplan context")
    )
    exten = models.CharField(
        max_length=40,
        verbose_name=_("Extension"),
        help_text=_("Extension pattern (e.g., 1001, _1XXX, s)")
    )
    priority = models.IntegerField(
        verbose_name=_("Priority"),
        help_text=_("Priority/step number in dialplan")
    )
    app = models.CharField(
        max_length=40,
        verbose_name=_("Application"),
        help_text=_("Asterisk application to execute (e.g., Dial, Playback, Hangup)")
    )
    appdata = models.CharField(
        max_length=512,
        blank=True,
        verbose_name=_("Application Data"),
        help_text=_("Arguments for the application")
    )
    
    def __str__(self):
        return f"{self.context},{self.exten},{self.priority}: {self.app}({self.appdata})"
