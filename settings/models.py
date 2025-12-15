import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class BannedCompanyName(models.Model):
    """
    Model representing a banned company name.

    This model is used to store company names that block the automatic generation
    of commercial requests from spam messages.
    Each name is unique and cannot be null or blank.

    Attributes:
        name (str): The name of the banned company, stored as a unique string
            with a maximum length of 50 characters.
    """
    class Meta:
        verbose_name = _("Banned company name")
        verbose_name_plural = _("Banned company names")

    name = models.CharField(
        max_length=50, unique=True,
        null=False, blank=False,
        verbose_name=_("Name")
    )

    def __str__(self):
        """
        Returns the string representation of the banned company name.
        """
        return self.name


class MassmailSettings(models.Model):
    """
    Model for mass mailing settings.
    """

    class Meta:
        verbose_name = _("Massmail Settings")
        verbose_name_plural = _("Massmail Settings")

    emails_per_day = models.PositiveIntegerField(
        default=94,
        help_text="Daily message limit for email accounts."
    )
    use_business_time = models.BooleanField(
        default=False,
        help_text="Send only during business hours."
    )
    business_time_start = models.TimeField(
        default="08:30",
        help_text="Start of working hours."
    )
    business_time_end = models.TimeField(
        default="17:30",
        help_text="End of working hours."
    )
    unsubscribe_url = models.URLField(
        default="https://www.example.com/unsubscribe",
        help_text='"Unsubscribed successfully" page."'
    )

    def __str__(self):
        return "Settings"


class PublicEmailDomain(models.Model):
    """
    Model representing a public email domain list.

    This model is used to store public domains to identify them in messages
    and prevent company identification by email domain.
    Each domain is unique and stored in the lowercase.

    Attributes:
        domain (str): The email domain, stored as a unique string with a
            maximum length of 20 characters.
    """
    class Meta:
        verbose_name = _('Public email domain')
        verbose_name_plural = _('Public email domains')

    domain = models.CharField(
        max_length=20, unique=True,
        null=False, blank=False,
        verbose_name=_("Domain")
    )

    def save(self, *args, **kwargs):
        """
        Overrides the save method to ensure the domain is stored in lowercase.
        """
        self.domain = self.domain.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        """
        Returns the string representation of the public email domain.
        """
        return self.domain


class Reminders(models.Model):
    """
    Model for storing reminder settings.

    This model is used to configure the interval at which reminders are checked.

    Attributes:
        check_interval (int): The interval in seconds to check for reminders,
            stored as a positive integer. Defaults to 300 seconds.
    """
    class Meta:
        verbose_name = _('Reminder settings')
        verbose_name_plural = _('Reminder settings')

    check_interval = models.PositiveBigIntegerField(
        null=False, blank=False,
        default='300',
        verbose_name=_("Check interval"),
        help_text=_(
            "Specify the interval in seconds to check if it's time for a reminder."
        )
    )

    def __str__(self):
        """
        Returns a string representation of the reminder settings.
        """
        return "Settings"


class StopPhrase(models.Model):
    """
    Model representing a stop phrase.

    This model is used to store phrases that block the automatic generation
    of commercial requests from spam messages. It also tracks the last
    occurrence date of each phrase.

    Attributes:
        phrase (str): The stop phrase, stored as a unique string with a
            maximum length of 100 characters.
        last_occurrence_date (date): The date when the phrase was most recently
            encountered, updated automatically whenever the record is saved.
    """
    class Meta:
        verbose_name = _('Stop Phrase')
        verbose_name_plural = _('Stop Phrases')

    phrase = models.CharField(
        max_length=100, unique=True,
        null=False, blank=False,
        verbose_name=_("Phrase")
    )
    last_occurrence_date = models.DateField(
        auto_now=True,
        verbose_name=_("Last occurrence date"),
        help_text=_("Date of last occurrence of the phrase")
    )

    def hit(self):
        """
        Updates the last occurrence date of the stop phrase to the current date.
        """
        self.save()

    def __str__(self):
        """
        Returns the string representation of the stop phrase.
        """
        return self.phrase


class SystemSettings(models.Model):
    """
    Model for storing general system settings.
    
    This is a singleton model - only one instance should exist.
    """
    class Meta:
        verbose_name = _('System Settings')
        verbose_name_plural = _('System Settings')

    company_name = models.CharField(
        max_length=255,
        default='',
        blank=True,
        verbose_name=_("Company Name")
    )
    company_email = models.EmailField(
        default='',
        blank=True,
        verbose_name=_("Company Email")
    )
    company_phone = models.CharField(
        max_length=50,
        default='',
        blank=True,
        verbose_name=_("Company Phone")
    )
    default_language = models.CharField(
        max_length=10,
        default='en',
        choices=[('en', 'English'), ('ru', 'Russian')],
        verbose_name=_("Default Language")
    )
    timezone = models.CharField(
        max_length=50,
        default='UTC',
        verbose_name=_("Timezone")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )

    def __str__(self):
        return "System Settings"


class APIKey(models.Model):
    """
    Model for API key management.
    
    Stores API keys for external integrations with permission scopes.
    """
    class Meta:
        verbose_name = _('API Key')
        verbose_name_plural = _('API Keys')
        ordering = ['-created_at']

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_("Name"),
        help_text=_("Descriptive name for this API key")
    )
    key = models.CharField(
        max_length=255,
        unique=True,
        verbose_name=_("API Key")
    )
    key_hash = models.CharField(
        max_length=255,
        verbose_name=_("Key Hash"),
        help_text=_("Hashed version of the key for secure storage")
    )
    permissions = models.JSONField(
        default=list,
        verbose_name=_("Permissions"),
        help_text=_("List of permission scopes for this key")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name=_("User")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    last_used = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Used")
    )
    usage_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Usage Count")
    )

    def __str__(self):
        return f"{self.name} - {self.key[:8]}..."

    @property
    def key_preview(self):
        """Returns a preview of the key (first 8 characters)."""
        return f"{self.key[:8]}..." if self.key else ""


class Webhook(models.Model):
    """
    Model for webhook configuration.
    
    Stores webhook URLs and events to trigger webhooks.
    """
    class Meta:
        verbose_name = _('Webhook')
        verbose_name_plural = _('Webhooks')
        ordering = ['-created_at']

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    url = models.URLField(
        verbose_name=_("URL"),
        help_text=_("The URL to send webhook POST requests to")
    )
    events = models.JSONField(
        default=list,
        verbose_name=_("Events"),
        help_text=_("List of events that trigger this webhook")
    )
    secret = models.CharField(
        max_length=255,
        verbose_name=_("Secret"),
        help_text=_("Secret key for HMAC signature verification")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )
    last_triggered = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last Triggered")
    )
    success_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Success Count")
    )
    failure_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Failure Count")
    )

    def __str__(self):
        return f"Webhook to {self.url}"


class WebhookDelivery(models.Model):
    """
    Model for tracking webhook delivery attempts.
    """
    class Meta:
        verbose_name = _('Webhook Delivery')
        verbose_name_plural = _('Webhook Deliveries')
        ordering = ['-created_at']

    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('success', _('Success')),
        ('failed', _('Failed')),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    webhook = models.ForeignKey(
        Webhook,
        on_delete=models.CASCADE,
        related_name='deliveries',
        verbose_name=_("Webhook")
    )
    event = models.CharField(
        max_length=100,
        verbose_name=_("Event")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("Status")
    )
    status_code = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("HTTP Status Code")
    )
    request_body = models.JSONField(
        verbose_name=_("Request Body")
    )
    response_body = models.TextField(
        blank=True,
        verbose_name=_("Response Body")
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_("Error Message")
    )
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Duration (ms)")
    )
    retry_count = models.PositiveIntegerField(
        default=0,
        verbose_name=_("Retry Count")
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created At")
    )

    def __str__(self):
        return f"{self.webhook} - {self.event} - {self.status}"


class IntegrationLog(models.Model):
    """
    Model for logging integration activities.
    
    Stores detailed logs of all integration requests and responses.
    """
    class Meta:
        verbose_name = _('Integration Log')
        verbose_name_plural = _('Integration Logs')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'integration']),
            models.Index(fields=['status']),
        ]

    STATUS_CHOICES = [
        ('success', _('Success')),
        ('error', _('Error')),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    integration = models.CharField(
        max_length=100,
        verbose_name=_("Integration"),
        help_text=_("Name of the integration (instagram, facebook, telegram, sms, voip)")
    )
    action = models.CharField(
        max_length=255,
        verbose_name=_("Action"),
        help_text=_("Action performed (e.g., message_received, message_sent)")
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        verbose_name=_("Status")
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Timestamp")
    )
    request_data = models.JSONField(
        default=dict,
        verbose_name=_("Request Data")
    )
    response_data = models.JSONField(
        default=dict,
        verbose_name=_("Response Data")
    )
    error_message = models.TextField(
        blank=True,
        verbose_name=_("Error Message")
    )
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Duration (ms)")
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='integration_logs',
        verbose_name=_("User")
    )
    stack_trace = models.TextField(
        blank=True,
        verbose_name=_("Stack Trace")
    )
    metadata = models.JSONField(
        default=dict,
        verbose_name=_("Metadata")
    )

    def __str__(self):
        return f"{self.integration} - {self.action} - {self.status}"


class NotificationSettings(models.Model):
    """
    Model for notification preferences.
    
    Can be global (user=None) or per-user.
    """
    class Meta:
        verbose_name = _('Notification Settings')
        verbose_name_plural = _('Notification Settings')

    FREQUENCY_CHOICES = [
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('never', _('Never')),
    ]

    user = models.OneToOneField(
        'auth.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notification_settings',
        verbose_name=_("User"),
        help_text=_("Leave blank for global settings")
    )
    notify_new_leads = models.BooleanField(
        default=True,
        verbose_name=_("Notify New Leads")
    )
    notify_missed_calls = models.BooleanField(
        default=True,
        verbose_name=_("Notify Missed Calls")
    )
    push_notifications = models.BooleanField(
        default=True,
        verbose_name=_("Push Notifications")
    )
    notify_task_assigned = models.BooleanField(
        default=True,
        verbose_name=_("Notify Task Assigned")
    )
    notify_deal_won = models.BooleanField(
        default=True,
        verbose_name=_("Notify Deal Won")
    )
    notify_message_received = models.BooleanField(
        default=True,
        verbose_name=_("Notify Message Received")
    )
    email_digest_frequency = models.CharField(
        max_length=10,
        choices=FREQUENCY_CHOICES,
        default='daily',
        verbose_name=_("Email Digest Frequency")
    )
    quiet_hours_start = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Quiet Hours Start")
    )
    quiet_hours_end = models.TimeField(
        null=True,
        blank=True,
        verbose_name=_("Quiet Hours End")
    )
    # Notification channels
    channel_email = models.BooleanField(
        default=True,
        verbose_name=_("Email Channel")
    )
    channel_sms = models.BooleanField(
        default=False,
        verbose_name=_("SMS Channel")
    )
    channel_push = models.BooleanField(
        default=True,
        verbose_name=_("Push Channel")
    )
    channel_telegram = models.BooleanField(
        default=False,
        verbose_name=_("Telegram Channel")
    )
    channel_in_app = models.BooleanField(
        default=True,
        verbose_name=_("In-App Channel")
    )

    def __str__(self):
        return f"Notification Settings for {self.user or 'Global'}"


class SecuritySettings(models.Model):
    """
    Model for security configuration.
    
    This is a singleton model - only one instance should exist.
    """
    class Meta:
        verbose_name = _('Security Settings')
        verbose_name_plural = _('Security Settings')

    ip_whitelist = models.TextField(
        blank=True,
        verbose_name=_("IP Whitelist"),
        help_text=_("One IP address per line. Leave blank to allow all.")
    )
    rate_limit = models.PositiveIntegerField(
        default=60,
        verbose_name=_("Rate Limit"),
        help_text=_("Maximum API requests per minute")
    )
    require_2fa = models.BooleanField(
        default=False,
        verbose_name=_("Require 2FA"),
        help_text=_("Require two-factor authentication for all users")
    )
    session_timeout = models.PositiveIntegerField(
        default=60,
        verbose_name=_("Session Timeout (minutes)"),
        help_text=_("Automatic logout after N minutes of inactivity")
    )
    # Password policy
    password_min_length = models.PositiveIntegerField(
        default=8,
        verbose_name=_("Password Min Length")
    )
    password_require_uppercase = models.BooleanField(
        default=True,
        verbose_name=_("Require Uppercase")
    )
    password_require_lowercase = models.BooleanField(
        default=True,
        verbose_name=_("Require Lowercase")
    )
    password_require_numbers = models.BooleanField(
        default=True,
        verbose_name=_("Require Numbers")
    )
    password_require_special = models.BooleanField(
        default=False,
        verbose_name=_("Require Special Characters")
    )
    password_expiry_days = models.PositiveIntegerField(
        default=90,
        verbose_name=_("Password Expiry (days)"),
        help_text=_("Set to 0 to disable password expiry")
    )
    # Login security
    login_attempts_limit = models.PositiveIntegerField(
        default=5,
        verbose_name=_("Login Attempts Limit")
    )
    lockout_duration = models.PositiveIntegerField(
        default=30,
        verbose_name=_("Lockout Duration (minutes)")
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated At")
    )

    def __str__(self):
        return "Security Settings"


# ============================================================================
# Social Media Integrations
# ============================================================================

class InstagramAccount(models.Model):
    """Instagram Business Account integration."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Account information
    instagram_user_id = models.CharField(max_length=100, unique=True)
    username = models.CharField(max_length=100)
    account_type = models.CharField(max_length=50, default='BUSINESS')
    
    # OAuth tokens
    access_token = models.TextField(help_text="Instagram Graph API access token")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Page information (Instagram Business Account connected to Facebook Page)
    facebook_page_id = models.CharField(max_length=100, blank=True)
    facebook_page_name = models.CharField(max_length=255, blank=True)
    
    # Connection settings
    is_active = models.BooleanField(default=True)
    auto_sync_messages = models.BooleanField(
        default=True,
        help_text="Automatically sync Instagram Direct messages"
    )
    auto_sync_comments = models.BooleanField(
        default=True,
        help_text="Automatically sync post comments"
    )
    
    # Webhook settings
    webhook_url = models.URLField(blank=True)
    webhook_verify_token = models.CharField(max_length=255, blank=True)
    
    # Statistics
    messages_synced = models.IntegerField(default=0)
    comments_synced = models.IntegerField(default=0)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    profile_picture_url = models.URLField(blank=True)
    followers_count = models.IntegerField(default=0)
    media_count = models.IntegerField(default=0)
    
    # User who connected this account
    connected_by = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='instagram_accounts'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Instagram Account")
        verbose_name_plural = _("Instagram Accounts")
    
    def __str__(self):
        return f"@{self.username}"
    
    def is_token_valid(self):
        """Check if access token is still valid."""
        if not self.token_expires_at:
            return True
        from django.utils import timezone
        return timezone.now() < self.token_expires_at


class FacebookPage(models.Model):
    """Facebook Page integration."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Page information
    facebook_page_id = models.CharField(max_length=100, unique=True)
    page_name = models.CharField(max_length=255)
    page_category = models.CharField(max_length=100, blank=True)
    
    # OAuth tokens
    access_token = models.TextField(help_text="Facebook Page access token")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    
    # Connection settings
    is_active = models.BooleanField(default=True)
    auto_sync_messages = models.BooleanField(
        default=True,
        help_text="Automatically sync Messenger messages"
    )
    auto_sync_comments = models.BooleanField(
        default=True,
        help_text="Automatically sync post comments"
    )
    auto_sync_posts = models.BooleanField(
        default=False,
        help_text="Automatically sync page posts"
    )
    
    # Webhook settings
    webhook_url = models.URLField(blank=True)
    webhook_verify_token = models.CharField(max_length=255, blank=True)
    
    # Statistics
    messages_synced = models.IntegerField(default=0)
    comments_synced = models.IntegerField(default=0)
    posts_synced = models.IntegerField(default=0)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    page_url = models.URLField(blank=True)
    profile_picture_url = models.URLField(blank=True)
    followers_count = models.IntegerField(default=0)
    
    # Permissions
    granted_permissions = models.JSONField(
        default=list,
        help_text="List of granted Facebook permissions"
    )
    
    # User who connected this page
    connected_by = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='facebook_pages'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Facebook Page")
        verbose_name_plural = _("Facebook Pages")
    
    def __str__(self):
        return self.page_name
    
    def is_token_valid(self):
        """Check if access token is still valid."""
        if not self.token_expires_at:
            return True
        from django.utils import timezone
        return timezone.now() < self.token_expires_at


class TelegramBot(models.Model):
    """Telegram Bot integration."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Bot information
    bot_token = models.CharField(
        max_length=100,
        unique=True,
        help_text="Telegram Bot API token"
    )
    bot_username = models.CharField(max_length=100)
    bot_name = models.CharField(max_length=255, blank=True)
    
    # Connection settings
    is_active = models.BooleanField(default=True)
    auto_reply = models.BooleanField(
        default=False,
        help_text="Enable automatic replies"
    )
    
    # Webhook settings
    webhook_url = models.URLField(
        blank=True,
        help_text="Telegram webhook URL for receiving updates"
    )
    webhook_secret_token = models.CharField(
        max_length=255,
        blank=True,
        help_text="Secret token for webhook validation"
    )
    use_webhook = models.BooleanField(
        default=True,
        help_text="Use webhook instead of polling"
    )
    
    # Statistics
    messages_received = models.IntegerField(default=0)
    messages_sent = models.IntegerField(default=0)
    active_chats = models.IntegerField(default=0)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    
    # Bot settings
    welcome_message = models.TextField(
        blank=True,
        help_text="Welcome message for new users"
    )
    commands = models.JSONField(
        default=dict,
        help_text="Custom bot commands configuration"
    )
    
    # Allowed chats (whitelist)
    allowed_chat_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of allowed Telegram chat IDs"
    )
    
    # User who connected this bot
    connected_by = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='telegram_bots'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = _("Telegram Bot")
        verbose_name_plural = _("Telegram Bots")
    
    def __str__(self):
        return f"@{self.bot_username}"
    
    def get_bot_info_url(self):
        """Get URL to view bot in Telegram."""
        return f"https://t.me/{self.bot_username}"
