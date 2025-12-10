# Generated migration for Asterisk Real-time models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('voip', '0013_call_routing_system'),
    ]

    operations = [
        # PJSIP Endpoints
        migrations.CreateModel(
            name='PsEndpoint',
            fields=[
                ('id', models.CharField(max_length=40, primary_key=True, serialize=False, verbose_name='Endpoint ID', help_text='Unique identifier for this endpoint')),
                ('transport', models.CharField(default='transport-udp', max_length=40, verbose_name='Transport', help_text='Transport to use (transport-udp, transport-tcp, transport-tls, transport-wss)')),
                ('aors', models.CharField(blank=True, max_length=200, verbose_name='AORs', help_text='Comma-separated list of AORs (Address of Records)')),
                ('auth', models.CharField(blank=True, max_length=40, verbose_name='Authentication', help_text='Authentication section name')),
                ('context', models.CharField(default='default', max_length=40, verbose_name='Context', help_text='Dialplan context for incoming calls')),
                ('disallow', models.CharField(default='all', max_length=200, verbose_name='Disallow Codecs', help_text='Codecs to disallow')),
                ('allow', models.CharField(default='ulaw,alaw,gsm', max_length=200, verbose_name='Allow Codecs', help_text='Codecs to allow (order matters)')),
                ('direct_media', models.CharField(default='no', max_length=3, verbose_name='Direct Media', help_text='Enable direct media between endpoints (yes/no)')),
                ('direct_media_method', models.CharField(blank=True, default='invite', max_length=20, verbose_name='Direct Media Method', help_text='Method for direct media (invite/reinvite/update)')),
                ('rtp_symmetric', models.CharField(default='yes', max_length=3, verbose_name='RTP Symmetric', help_text='Send RTP to source of received RTP')),
                ('force_rport', models.CharField(default='yes', max_length=3, verbose_name='Force rport', help_text='Force rport to be added for NAT')),
                ('rewrite_contact', models.CharField(default='yes', max_length=3, verbose_name='Rewrite Contact', help_text='Rewrite contact header for NAT')),
                ('dtmf_mode', models.CharField(default='rfc4733', max_length=10, verbose_name='DTMF Mode', help_text='DTMF transmission mode (rfc4733/inband/info/auto)')),
                ('callerid', models.CharField(blank=True, max_length=80, verbose_name='Caller ID', help_text='Caller ID in format "Name" <number>')),
                ('callerid_privacy', models.CharField(blank=True, max_length=20, verbose_name='Caller ID Privacy', help_text='Caller ID privacy setting')),
                ('callerid_tag', models.CharField(blank=True, max_length=40, verbose_name='Caller ID Tag', help_text='Caller ID tag')),
                ('max_audio_streams', models.IntegerField(default=1, verbose_name='Max Audio Streams')),
                ('max_video_streams', models.IntegerField(default=0, verbose_name='Max Video Streams')),
                ('device_state_busy_at', models.IntegerField(default=0, verbose_name='Device State Busy At', help_text='Number of in-use channels before device state is \'busy\' (0=disabled)')),
                ('timers', models.CharField(default='yes', max_length=3, verbose_name='Session Timers', help_text='Enable session timers')),
                ('timers_min_se', models.IntegerField(default=90, verbose_name='Timers Min SE', help_text='Minimum session timer expiration (seconds)')),
                ('timers_sess_expires', models.IntegerField(default=1800, verbose_name='Timers Session Expires', help_text='Session timer expiration (seconds)')),
                ('media_encryption', models.CharField(default='no', max_length=10, verbose_name='Media Encryption', help_text='Media encryption method (no/sdes/dtls)')),
                ('media_encryption_optimistic', models.CharField(default='no', max_length=3, verbose_name='Media Encryption Optimistic', help_text='Use optimistic encryption')),
                ('use_ptime', models.CharField(default='no', max_length=3, verbose_name='Use ptime', help_text='Use ptime attribute in SDP')),
                ('ice_support', models.CharField(default='no', max_length=3, verbose_name='ICE Support', help_text='Enable ICE support')),
                ('record_on_feature', models.CharField(blank=True, max_length=40, verbose_name='Record On Feature', help_text='Feature code to start recording')),
                ('record_off_feature', models.CharField(blank=True, max_length=40, verbose_name='Record Off Feature', help_text='Feature code to stop recording')),
                ('mailboxes', models.CharField(blank=True, max_length=200, verbose_name='Mailboxes', help_text='Mailboxes for MWI (Message Waiting Indication)')),
                ('mwi_subscribe_replaces_unsolicited', models.CharField(default='no', max_length=3, verbose_name='MWI Subscribe Replaces Unsolicited')),
                ('allow_subscribe', models.CharField(default='yes', max_length=3, verbose_name='Allow Subscribe', help_text='Allow subscriptions')),
                ('sub_min_expiry', models.IntegerField(default=60, verbose_name='Subscription Min Expiry')),
                ('t38_udptl', models.CharField(default='no', max_length=3, verbose_name='T.38 UDPTL', help_text='Enable T.38 fax support')),
                ('t38_udptl_ec', models.CharField(default='none', max_length=20, verbose_name='T.38 Error Correction', help_text='T.38 error correction method')),
                ('t38_udptl_maxdatagram', models.IntegerField(default=400, verbose_name='T.38 Max Datagram')),
                ('codec_prefs_incoming_offer', models.CharField(blank=True, default='prefer:pending,operation:union', max_length=20, verbose_name='Codec Prefs Incoming Offer')),
                ('codec_prefs_outgoing_offer', models.CharField(blank=True, default='prefer:pending,operation:intersect', max_length=20, verbose_name='Codec Prefs Outgoing Offer')),
                ('codec_prefs_incoming_answer', models.CharField(blank=True, default='prefer:pending,operation:intersect', max_length=20, verbose_name='Codec Prefs Incoming Answer')),
                ('send_pai', models.CharField(default='no', max_length=3, verbose_name='Send PAI', help_text='Send P-Asserted-Identity header')),
                ('send_rpid', models.CharField(default='no', max_length=3, verbose_name='Send RPID', help_text='Send Remote-Party-ID header')),
                ('trust_id_inbound', models.CharField(default='no', max_length=3, verbose_name='Trust ID Inbound')),
                ('trust_id_outbound', models.CharField(default='no', max_length=3, verbose_name='Trust ID Outbound')),
                ('crm_user', models.OneToOneField(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='asterisk_endpoint', to=settings.AUTH_USER_MODEL, verbose_name='CRM User')),
            ],
            options={
                'verbose_name': 'PJSIP Endpoint',
                'verbose_name_plural': 'PJSIP Endpoints',
                'db_table': 'ps_endpoints',
            },
        ),
        
        # PJSIP Authentication
        migrations.CreateModel(
            name='PsAuth',
            fields=[
                ('id', models.CharField(max_length=40, primary_key=True, serialize=False, verbose_name='Auth ID', help_text='Authentication identifier (usually matches endpoint)')),
                ('auth_type', models.CharField(default='userpass', max_length=10, verbose_name='Auth Type', help_text='Authentication type (userpass/md5)')),
                ('password', models.CharField(max_length=80, verbose_name='Password', help_text='Password for authentication')),
                ('username', models.CharField(max_length=40, verbose_name='Username', help_text='Username for authentication')),
                ('realm', models.CharField(blank=True, max_length=40, verbose_name='Realm', help_text='Authentication realm (optional)')),
                ('nonce_lifetime', models.IntegerField(default=32, verbose_name='Nonce Lifetime', help_text='Lifetime of nonce in seconds')),
                ('md5_cred', models.CharField(blank=True, max_length=100, verbose_name='MD5 Credentials', help_text='MD5 hash credentials (for md5 auth type)')),
            ],
            options={
                'verbose_name': 'PJSIP Auth',
                'verbose_name_plural': 'PJSIP Auths',
                'db_table': 'ps_auths',
            },
        ),
        
        # PJSIP AOR (Address of Record)
        migrations.CreateModel(
            name='PsAor',
            fields=[
                ('id', models.CharField(max_length=40, primary_key=True, serialize=False, verbose_name='AOR ID', help_text='Address of Record identifier')),
                ('max_contacts', models.IntegerField(default=1, verbose_name='Max Contacts', help_text='Maximum number of contacts for this AOR')),
                ('remove_existing', models.CharField(default='yes', max_length=3, verbose_name='Remove Existing', help_text='Remove existing contacts on new registration')),
                ('minimum_expiration', models.IntegerField(default=60, verbose_name='Minimum Expiration', help_text='Minimum registration expiration time (seconds)')),
                ('maximum_expiration', models.IntegerField(default=3600, verbose_name='Maximum Expiration', help_text='Maximum registration expiration time (seconds)')),
                ('default_expiration', models.IntegerField(default=3600, verbose_name='Default Expiration', help_text='Default registration expiration time (seconds)')),
                ('qualify_frequency', models.IntegerField(default=0, verbose_name='Qualify Frequency', help_text='Frequency to qualify endpoint (seconds, 0=disabled)')),
                ('qualify_timeout', models.FloatField(default=3.0, verbose_name='Qualify Timeout', help_text='Timeout for qualify requests (seconds)')),
                ('authenticate_qualify', models.CharField(default='no', max_length=3, verbose_name='Authenticate Qualify', help_text='Authenticate qualify requests')),
                ('support_path', models.CharField(default='no', max_length=3, verbose_name='Support Path', help_text='Support Path header for registration')),
                ('outbound_proxy', models.CharField(blank=True, max_length=256, verbose_name='Outbound Proxy', help_text='Outbound proxy for requests')),
                ('mailboxes', models.CharField(blank=True, max_length=200, verbose_name='Mailboxes', help_text='Mailboxes for this AOR')),
            ],
            options={
                'verbose_name': 'PJSIP AOR',
                'verbose_name_plural': 'PJSIP AORs',
                'db_table': 'ps_aors',
            },
        ),
        
        # PJSIP Contacts (dynamic)
        migrations.CreateModel(
            name='PsContact',
            fields=[
                ('id', models.CharField(max_length=255, primary_key=True, serialize=False, verbose_name='Contact ID')),
                ('endpoint', models.CharField(max_length=40, verbose_name='Endpoint', help_text='Associated endpoint')),
                ('uri', models.CharField(max_length=511, verbose_name='URI', help_text='Contact URI')),
                ('expiration_time', models.BigIntegerField(verbose_name='Expiration Time', help_text='Unix timestamp when registration expires')),
                ('qualify_frequency', models.IntegerField(default=0, verbose_name='Qualify Frequency')),
                ('qualify_timeout', models.FloatField(default=3.0, verbose_name='Qualify Timeout')),
                ('authenticate_qualify', models.CharField(default='no', max_length=3, verbose_name='Authenticate Qualify')),
                ('outbound_proxy', models.CharField(blank=True, max_length=256, verbose_name='Outbound Proxy')),
                ('path', models.TextField(blank=True, verbose_name='Path', help_text='Path header from registration')),
                ('user_agent', models.CharField(blank=True, max_length=255, verbose_name='User Agent')),
                ('reg_server', models.CharField(blank=True, max_length=255, verbose_name='Registration Server')),
            ],
            options={
                'verbose_name': 'PJSIP Contact',
                'verbose_name_plural': 'PJSIP Contacts',
                'db_table': 'ps_contacts',
            },
        ),
        
        # PJSIP Identify (IP-based identification)
        migrations.CreateModel(
            name='PsIdentify',
            fields=[
                ('id', models.CharField(max_length=40, primary_key=True, serialize=False, verbose_name='Identify ID')),
                ('endpoint', models.CharField(max_length=40, verbose_name='Endpoint', help_text='Endpoint to associate with this identification')),
                ('match', models.CharField(max_length=80, verbose_name='Match', help_text='IP address or network to match (e.g., 192.168.1.10, 192.168.1.0/24)')),
                ('srv_lookups', models.CharField(default='yes', max_length=3, verbose_name='SRV Lookups', help_text='Enable SRV lookups')),
                ('match_header', models.CharField(blank=True, max_length=255, verbose_name='Match Header', help_text='SIP header to match')),
            ],
            options={
                'verbose_name': 'PJSIP Identify',
                'verbose_name_plural': 'PJSIP Identifies',
                'db_table': 'ps_endpoint_id_ips',
            },
        ),
        
        # PJSIP Transport
        migrations.CreateModel(
            name='PsTransport',
            fields=[
                ('id', models.CharField(max_length=40, primary_key=True, serialize=False, verbose_name='Transport ID')),
                ('protocol', models.CharField(default='udp', max_length=10, verbose_name='Protocol', help_text='Transport protocol (udp/tcp/tls/ws/wss)')),
                ('bind', models.CharField(max_length=255, verbose_name='Bind', help_text='IP:port to bind to (e.g., 0.0.0.0:5060)')),
                ('external_media_address', models.CharField(blank=True, max_length=255, verbose_name='External Media Address', help_text='External IP for media (NAT)')),
                ('external_signaling_address', models.CharField(blank=True, max_length=255, verbose_name='External Signaling Address', help_text='External IP for signaling (NAT)')),
                ('local_net', models.CharField(blank=True, max_length=255, verbose_name='Local Network', help_text='Local network CIDR (e.g., 192.168.0.0/16)')),
                ('cert_file', models.CharField(blank=True, max_length=255, verbose_name='Certificate File', help_text='Path to SSL certificate file')),
                ('priv_key_file', models.CharField(blank=True, max_length=255, verbose_name='Private Key File', help_text='Path to SSL private key file')),
                ('ca_list_file', models.CharField(blank=True, max_length=255, verbose_name='CA List File', help_text='Path to CA certificate list file')),
                ('verify_server', models.CharField(default='no', max_length=3, verbose_name='Verify Server', help_text='Verify server certificate')),
                ('verify_client', models.CharField(default='no', max_length=3, verbose_name='Verify Client', help_text='Verify client certificate')),
                ('require_client_cert', models.CharField(default='no', max_length=3, verbose_name='Require Client Cert')),
                ('method', models.CharField(blank=True, default='tlsv1_2', max_length=10, verbose_name='SSL/TLS Method', help_text='SSL/TLS method (sslv23/tlsv1/tlsv1_1/tlsv1_2)')),
                ('cipher', models.CharField(blank=True, max_length=255, verbose_name='Cipher Suite', help_text='OpenSSL cipher suite')),
                ('websocket_write_timeout', models.IntegerField(default=100, verbose_name='WebSocket Write Timeout', help_text='WebSocket write timeout in milliseconds')),
            ],
            options={
                'verbose_name': 'PJSIP Transport',
                'verbose_name_plural': 'PJSIP Transports',
                'db_table': 'ps_transports',
            },
        ),
        
        # Dialplan Extensions
        migrations.CreateModel(
            name='Extension',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('context', models.CharField(max_length=40, verbose_name='Context', help_text='Dialplan context')),
                ('exten', models.CharField(max_length=40, verbose_name='Extension', help_text='Extension pattern (e.g., 1001, _1XXX, s)')),
                ('priority', models.IntegerField(verbose_name='Priority', help_text='Priority/step number in dialplan')),
                ('app', models.CharField(max_length=40, verbose_name='Application', help_text='Asterisk application to execute (e.g., Dial, Playback, Hangup)')),
                ('appdata', models.CharField(blank=True, max_length=512, verbose_name='Application Data', help_text='Arguments for the application')),
            ],
            options={
                'verbose_name': 'Dialplan Extension',
                'verbose_name_plural': 'Dialplan Extensions',
                'db_table': 'extensions',
                'ordering': ['context', 'priority'],
            },
        ),
        
        # Indexes for performance
        migrations.AddIndex(
            model_name='psendpoint',
            index=models.Index(fields=['id'], name='ps_endpoint_id_idx'),
        ),
        migrations.AddIndex(
            model_name='psauth',
            index=models.Index(fields=['id'], name='ps_auths_id_idx'),
        ),
        migrations.AddIndex(
            model_name='psaor',
            index=models.Index(fields=['id'], name='ps_aors_id_idx'),
        ),
        migrations.AddIndex(
            model_name='pscontact',
            index=models.Index(fields=['id'], name='ps_contacts_id_idx'),
        ),
        migrations.AddIndex(
            model_name='pscontact',
            index=models.Index(fields=['endpoint'], name='ps_contacts_endpoint_idx'),
        ),
        migrations.AddIndex(
            model_name='psidentify',
            index=models.Index(fields=['id'], name='ps_identify_id_idx'),
        ),
        migrations.AddIndex(
            model_name='psidentify',
            index=models.Index(fields=['endpoint'], name='ps_identify_endpoint_idx'),
        ),
        migrations.AddIndex(
            model_name='pstransport',
            index=models.Index(fields=['id'], name='ps_transports_id_idx'),
        ),
        migrations.AddIndex(
            model_name='extension',
            index=models.Index(fields=['context', 'exten', 'priority'], name='extensions_lookup_idx'),
        ),
    ]
