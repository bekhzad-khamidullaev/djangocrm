from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

User = get_user_model()


class AuthenticationLog(models.Model):
    """Log authentication attempts for monitoring JWT vs legacy token usage"""
    
    AUTH_TYPE_CHOICES = [
        ('jwt', 'JWT'),
        ('legacy', 'Legacy Token'),
        ('session', 'Session'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auth_logs',
        verbose_name=_('User')
    )
    username = models.CharField(
        max_length=150,
        verbose_name=_('Username'),
        help_text=_('Username attempted (stored even if auth failed)')
    )
    auth_type = models.CharField(
        max_length=20,
        choices=AUTH_TYPE_CHOICES,
        verbose_name=_('Authentication Type')
    )
    endpoint = models.CharField(
        max_length=255,
        verbose_name=_('Endpoint'),
        help_text=_('API endpoint accessed')
    )
    method = models.CharField(
        max_length=10,
        verbose_name=_('HTTP Method'),
        default='GET'
    )
    success = models.BooleanField(
        default=True,
        verbose_name=_('Success')
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name=_('IP Address')
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name=_('User Agent')
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_('Timestamp'),
        db_index=True
    )
    
    class Meta:
        verbose_name = _('Authentication Log')
        verbose_name_plural = _('Authentication Logs')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp', 'auth_type']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['auth_type', 'success']),
        ]
    
    def __str__(self):
        return f"{self.username} - {self.auth_type} - {self.timestamp}"
