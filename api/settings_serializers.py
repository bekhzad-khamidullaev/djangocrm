"""
Serializers for CRM Settings API endpoints.
"""
import secrets
import hashlib
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone

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

User = get_user_model()


class SystemSettingsSerializer(serializers.ModelSerializer):
    """Serializer for general system settings."""
    
    class Meta:
        model = SystemSettings
        fields = [
            'id',
            'company_name',
            'company_email',
            'company_phone',
            'default_language',
            'timezone',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class APIKeySerializer(serializers.ModelSerializer):
    """Serializer for API keys (list/retrieve)."""
    key_preview = serializers.CharField(read_only=True)
    
    class Meta:
        model = APIKey
        fields = [
            'id',
            'name',
            'key_preview',
            'permissions',
            'is_active',
            'created_at',
            'last_used',
            'usage_count',
        ]
        read_only_fields = ['id', 'key_preview', 'created_at', 'last_used', 'usage_count']


class APIKeyCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating API keys (includes full key in response)."""
    key = serializers.CharField(read_only=True)
    key_preview = serializers.CharField(read_only=True)
    
    class Meta:
        model = APIKey
        fields = [
            'id',
            'name',
            'key',
            'key_preview',
            'permissions',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'key', 'key_preview', 'created_at']
    
    def create(self, validated_data):
        """Generate a secure API key on creation."""
        # Generate a random API key
        key = f"sk_{'live' if not self.context.get('test_mode') else 'test'}_{secrets.token_urlsafe(32)}"
        
        # Hash the key for secure storage
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        
        # Create the API key instance
        api_key = APIKey.objects.create(
            key=key,
            key_hash=key_hash,
            user=self.context['request'].user,
            **validated_data
        )
        
        return api_key


class APIKeyUsageSerializer(serializers.Serializer):
    """Serializer for API key usage statistics."""
    key_id = serializers.UUIDField()
    total_requests = serializers.IntegerField()
    last_7_days = serializers.ListField(
        child=serializers.DictField()
    )
    endpoints_used = serializers.ListField(
        child=serializers.DictField()
    )


class WebhookSerializer(serializers.ModelSerializer):
    """Serializer for webhooks (list/retrieve - secret is masked)."""
    secret_preview = serializers.SerializerMethodField()
    
    class Meta:
        model = Webhook
        fields = [
            'id',
            'url',
            'events',
            'secret_preview',
            'is_active',
            'created_at',
            'last_triggered',
            'success_count',
            'failure_count',
        ]
        read_only_fields = ['id', 'secret_preview', 'created_at', 'last_triggered', 'success_count', 'failure_count']
    
    def get_secret_preview(self, obj):
        """Return masked preview of secret."""
        if obj.secret:
            return f"{obj.secret[:10]}..." if len(obj.secret) > 10 else "***"
        return None


class WebhookCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating webhooks (includes secret in response)."""
    
    class Meta:
        model = Webhook
        fields = [
            'id',
            'url',
            'events',
            'secret',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'secret', 'created_at']
    
    def create(self, validated_data):
        """Generate a secret for webhook signature verification."""
        if 'secret' not in validated_data or not validated_data['secret']:
            validated_data['secret'] = f"whsec_{secrets.token_urlsafe(32)}"
        return super().create(validated_data)


class WebhookDeliverySerializer(serializers.ModelSerializer):
    """Serializer for webhook deliveries."""
    
    class Meta:
        model = WebhookDelivery
        fields = [
            'id',
            'webhook',
            'event',
            'status',
            'status_code',
            'request_body',
            'response_body',
            'error_message',
            'duration_ms',
            'retry_count',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class IntegrationLogSerializer(serializers.ModelSerializer):
    """Serializer for integration logs."""
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    
    class Meta:
        model = IntegrationLog
        fields = [
            'id',
            'integration',
            'action',
            'status',
            'timestamp',
            'request_data',
            'response_data',
            'error_message',
            'duration_ms',
            'user',
            'user_email',
            'stack_trace',
            'metadata',
        ]
        read_only_fields = ['id', 'timestamp', 'user_email']


class IntegrationLogStatsSerializer(serializers.Serializer):
    """Serializer for integration log statistics."""
    by_integration = serializers.ListField(
        child=serializers.DictField()
    )
    by_status = serializers.DictField()
    timeline = serializers.ListField(
        child=serializers.DictField()
    )


class NotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for notification settings."""
    notification_channels = serializers.SerializerMethodField()
    
    class Meta:
        model = NotificationSettings
        fields = [
            'id',
            'user',
            'notify_new_leads',
            'notify_missed_calls',
            'push_notifications',
            'notify_task_assigned',
            'notify_deal_won',
            'notify_message_received',
            'email_digest_frequency',
            'quiet_hours_start',
            'quiet_hours_end',
            'notification_channels',
        ]
        read_only_fields = ['id']
    
    def get_notification_channels(self, obj):
        """Return notification channels as a dict."""
        return {
            'email': obj.channel_email,
            'sms': obj.channel_sms,
            'push': obj.channel_push,
            'telegram': obj.channel_telegram,
            'in_app': obj.channel_in_app,
        }
    
    def update(self, instance, validated_data):
        """Handle notification channels if provided."""
        # Extract notification_channels from validated_data if present in request
        request_data = self.context.get('request').data if self.context.get('request') else {}
        channels = request_data.get('notification_channels', {})
        
        if channels:
            instance.channel_email = channels.get('email', instance.channel_email)
            instance.channel_sms = channels.get('sms', instance.channel_sms)
            instance.channel_push = channels.get('push', instance.channel_push)
            instance.channel_telegram = channels.get('telegram', instance.channel_telegram)
            instance.channel_in_app = channels.get('in_app', instance.channel_in_app)
        
        return super().update(instance, validated_data)


class SecuritySettingsSerializer(serializers.ModelSerializer):
    """Serializer for security settings."""
    password_policy = serializers.SerializerMethodField()
    login_security = serializers.SerializerMethodField()
    ip_whitelist_list = serializers.SerializerMethodField()
    
    class Meta:
        model = SecuritySettings
        fields = [
            'id',
            'ip_whitelist',
            'ip_whitelist_list',
            'rate_limit',
            'require_2fa',
            'session_timeout',
            'password_policy',
            'login_security',
            'updated_at',
        ]
        read_only_fields = ['id', 'updated_at', 'ip_whitelist_list', 'password_policy', 'login_security']
    
    def get_password_policy(self, obj):
        """Return password policy as a dict."""
        return {
            'min_length': obj.password_min_length,
            'require_uppercase': obj.password_require_uppercase,
            'require_lowercase': obj.password_require_lowercase,
            'require_numbers': obj.password_require_numbers,
            'require_special': obj.password_require_special,
            'expiry_days': obj.password_expiry_days,
        }
    
    def get_login_security(self, obj):
        """Return login security settings as a dict."""
        return {
            'attempts_limit': obj.login_attempts_limit,
            'lockout_duration': obj.lockout_duration,
        }
    
    def get_ip_whitelist_list(self, obj):
        """Return IP whitelist as a list."""
        if not obj.ip_whitelist:
            return []
        return [ip.strip() for ip in obj.ip_whitelist.split('\n') if ip.strip()]
    
    def update(self, instance, validated_data):
        """Handle nested password_policy and login_security updates."""
        request_data = self.context.get('request').data if self.context.get('request') else {}
        
        # Handle password_policy
        password_policy = request_data.get('password_policy', {})
        if password_policy:
            instance.password_min_length = password_policy.get('min_length', instance.password_min_length)
            instance.password_require_uppercase = password_policy.get('require_uppercase', instance.password_require_uppercase)
            instance.password_require_lowercase = password_policy.get('require_lowercase', instance.password_require_lowercase)
            instance.password_require_numbers = password_policy.get('require_numbers', instance.password_require_numbers)
            instance.password_require_special = password_policy.get('require_special', instance.password_require_special)
            instance.password_expiry_days = password_policy.get('expiry_days', instance.password_expiry_days)
        
        # Handle login_security
        login_security = request_data.get('login_security', {})
        if login_security:
            instance.login_attempts_limit = login_security.get('attempts_limit', instance.login_attempts_limit)
            instance.lockout_duration = login_security.get('lockout_duration', instance.lockout_duration)
        
        return super().update(instance, validated_data)


class ActiveSessionSerializer(serializers.ModelSerializer):
    """Serializer for active user sessions."""
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    class Meta:
        model = UserSession
        fields = [
            'session_key',
            'user_id',
            'user_email',
            'ip_address',
            'user_agent',
            'device_name',
            'last_activity',
            'created_at',
        ]
        read_only_fields = fields


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for security audit logs."""
    user_email = serializers.EmailField(source='user.email', read_only=True, allow_null=True)
    details = serializers.SerializerMethodField()
    
    class Meta:
        model = AuthenticationLog
        fields = [
            'id',
            'user_id',
            'user_email',
            'username',
            'auth_type',
            'endpoint',
            'method',
            'success',
            'ip_address',
            'user_agent',
            'timestamp',
            'details',
        ]
        read_only_fields = fields
    
    def get_details(self, obj):
        """Return additional details as JSON."""
        return {
            'auth_type': obj.auth_type,
            'endpoint': obj.endpoint,
            'method': obj.method,
        }


class TestNotificationSerializer(serializers.Serializer):
    """Serializer for testing notifications."""
    channel = serializers.ChoiceField(
        choices=['email', 'sms', 'push', 'telegram'],
        required=True
    )
    recipient = serializers.CharField(required=True)
    
    def validate(self, data):
        """Validate the recipient based on channel type."""
        channel = data['channel']
        recipient = data['recipient']
        
        if channel == 'email':
            # Validate email format
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError
            try:
                validate_email(recipient)
            except ValidationError:
                raise serializers.ValidationError({'recipient': 'Invalid email address'})
        
        return data


# ============================================================================
# Social Media Integration Serializers
# ============================================================================

from settings.models import InstagramAccount, FacebookPage, TelegramBot


class InstagramAccountSerializer(serializers.ModelSerializer):
    """Serializer for Instagram Account."""
    
    connected_by_username = serializers.CharField(
        source='connected_by.username',
        read_only=True
    )
    is_token_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = InstagramAccount
        fields = [
            'id', 'instagram_user_id', 'username', 'account_type',
            'facebook_page_id', 'facebook_page_name',
            'is_active', 'auto_sync_messages', 'auto_sync_comments',
            'webhook_url', 'messages_synced', 'comments_synced', 'last_sync_at',
            'profile_picture_url', 'followers_count', 'media_count',
            'connected_by_username', 'is_token_valid',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'messages_synced', 'comments_synced', 'last_sync_at',
            'followers_count', 'media_count', 'created_at', 'updated_at',
            'connected_by_username'
        ]
    
    def get_is_token_valid(self, obj):
        """Check if token is still valid."""
        return obj.is_token_valid()


class InstagramAccountCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Instagram Account with OAuth."""
    
    access_token = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = InstagramAccount
        fields = [
            'instagram_user_id', 'username', 'access_token',
            'token_expires_at', 'facebook_page_id', 'facebook_page_name',
            'auto_sync_messages', 'auto_sync_comments'
        ]
    
    def create(self, validated_data):
        """Create Instagram account with connected_by."""
        request = self.context.get('request')
        validated_data['connected_by'] = request.user
        return super().create(validated_data)


class FacebookPageSerializer(serializers.ModelSerializer):
    """Serializer for Facebook Page."""
    
    connected_by_username = serializers.CharField(
        source='connected_by.username',
        read_only=True
    )
    is_token_valid = serializers.SerializerMethodField()
    
    class Meta:
        model = FacebookPage
        fields = [
            'id', 'facebook_page_id', 'page_name', 'page_category',
            'is_active', 'auto_sync_messages', 'auto_sync_comments', 'auto_sync_posts',
            'webhook_url', 'messages_synced', 'comments_synced', 'posts_synced', 
            'last_sync_at', 'page_url', 'profile_picture_url', 'followers_count',
            'granted_permissions', 'connected_by_username', 'is_token_valid',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'messages_synced', 'comments_synced', 'posts_synced',
            'last_sync_at', 'followers_count', 'created_at', 'updated_at',
            'connected_by_username'
        ]
    
    def get_is_token_valid(self, obj):
        """Check if token is still valid."""
        return obj.is_token_valid()


class FacebookPageCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Facebook Page with OAuth."""
    
    access_token = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = FacebookPage
        fields = [
            'facebook_page_id', 'page_name', 'page_category',
            'access_token', 'token_expires_at',
            'auto_sync_messages', 'auto_sync_comments', 'auto_sync_posts',
            'granted_permissions'
        ]
    
    def create(self, validated_data):
        """Create Facebook page with connected_by."""
        request = self.context.get('request')
        validated_data['connected_by'] = request.user
        return super().create(validated_data)


class TelegramBotSerializer(serializers.ModelSerializer):
    """Serializer for Telegram Bot."""
    
    connected_by_username = serializers.CharField(
        source='connected_by.username',
        read_only=True
    )
    bot_info_url = serializers.SerializerMethodField()
    
    class Meta:
        model = TelegramBot
        fields = [
            'id', 'bot_username', 'bot_name',
            'is_active', 'auto_reply', 'use_webhook',
            'webhook_url', 'messages_received', 'messages_sent',
            'active_chats', 'last_activity_at',
            'welcome_message', 'commands', 'allowed_chat_ids',
            'connected_by_username', 'bot_info_url',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'bot_username', 'bot_name',
            'messages_received', 'messages_sent', 'active_chats',
            'last_activity_at', 'created_at', 'updated_at',
            'connected_by_username', 'bot_info_url'
        ]
    
    def get_bot_info_url(self, obj):
        """Get Telegram bot URL."""
        return obj.get_bot_info_url()


class TelegramBotCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating Telegram Bot."""
    
    bot_token = serializers.CharField(write_only=True, required=True)
    
    class Meta:
        model = TelegramBot
        fields = [
            'bot_token', 'welcome_message', 'commands',
            'auto_reply', 'use_webhook', 'allowed_chat_ids'
        ]
    
    def validate_bot_token(self, value):
        """Validate Telegram bot token format."""
        import re
        # Telegram bot token format: {bot_id}:{token_hash}
        # bot_id: digits, token_hash: alphanumeric and special chars (30+ chars)
        pattern = r'^\d+:[A-Za-z0-9_\-]{30,}$'
        if not re.match(pattern, value):
            raise serializers.ValidationError(
                "Invalid Telegram bot token format. "
                "Expected format: 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
            )
        return value
    
    def create(self, validated_data):
        """Create Telegram bot with connected_by and fetch bot info."""
        request = self.context.get('request')
        validated_data['connected_by'] = request.user
        
        # Extract bot ID from token for placeholder username
        bot_token = validated_data['bot_token']
        bot_id = bot_token.split(':')[0]
        validated_data['bot_username'] = f"bot_{bot_id}"
        validated_data['bot_name'] = f"Bot {bot_id}"
        
        return super().create(validated_data)
