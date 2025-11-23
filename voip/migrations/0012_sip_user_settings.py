# Generated manually for SIP user settings

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('voip', '0005_alter_connection_provider_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SipServer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Display name for this SIP server', max_length=100, verbose_name='Server Name')),
                ('host', models.CharField(help_text='Domain or IP address of SIP server', max_length=255, verbose_name='SIP Server Host')),
                ('websocket_uri', models.CharField(help_text='WSS URI for WebRTC connection (e.g., wss://sip.example.com:7443)', max_length=255, verbose_name='WebSocket URI')),
                ('realm', models.CharField(blank=True, help_text='SIP realm, usually same as host', max_length=255, verbose_name='Realm')),
                ('proxy', models.CharField(blank=True, help_text='Optional outbound proxy server', max_length=255, verbose_name='Outbound Proxy')),
                ('register_expires', models.PositiveIntegerField(default=600, help_text='Registration expiry time in seconds', verbose_name='Registration Expires')),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'SIP Server',
                'verbose_name_plural': 'SIP Servers',
            },
        ),
        migrations.CreateModel(
            name='InternalNumber',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(help_text='Internal extension number (e.g., 1001, 2005)', max_length=20, verbose_name='Internal Number')),
                ('password', models.CharField(help_text='SIP authentication password', max_length=255, verbose_name='SIP Password')),
                ('display_name', models.CharField(blank=True, help_text='Name to display in calls', max_length=100, verbose_name='Display Name')),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
                ('auto_generated', models.BooleanField(default=False, help_text='Whether this number was auto-generated', verbose_name='Auto Generated')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='internal_numbers', to='voip.sipserver', verbose_name='SIP Server')),
                ('user', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='internal_number', to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'Internal Number',
                'verbose_name_plural': 'Internal Numbers',
            },
        ),
        migrations.CreateModel(
            name='SipAccount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_caller_id', models.CharField(blank=True, help_text='Phone number to show for outbound calls', max_length=50, verbose_name='External Caller ID')),
                ('can_make_external_calls', models.BooleanField(default=False, verbose_name='Can Make External Calls')),
                ('can_receive_external_calls', models.BooleanField(default=False, verbose_name='Can Receive External Calls')),
                ('call_recording_enabled', models.BooleanField(default=True, verbose_name='Call Recording Enabled')),
                ('voicemail_enabled', models.BooleanField(default=True, verbose_name='Voicemail Enabled')),
                ('voicemail_email', models.EmailField(blank=True, help_text='Email to send voicemail notifications', max_length=254, verbose_name='Voicemail Email')),
                ('max_concurrent_calls', models.PositiveIntegerField(default=2, verbose_name='Max Concurrent Calls')),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('internal_number', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='sip_account', to='voip.internalnumber', verbose_name='Internal Number')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='sip_account', to=settings.AUTH_USER_MODEL, verbose_name='User')),
            ],
            options={
                'verbose_name': 'SIP Account',
                'verbose_name_plural': 'SIP Accounts',
            },
        ),
        migrations.AlterUniqueTogether(
            name='internalnumber',
            unique_together={('server', 'number')},
        ),
    ]