# Generated manually for call routing system

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('voip', '0012_sip_user_settings'),
    ]

    operations = [
        migrations.CreateModel(
            name='NumberGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Display name for this group (e.g., Sales, Support, Management)', max_length=100, verbose_name='Group Name')),
                ('description', models.TextField(blank=True, help_text="Description of this group's purpose", verbose_name='Description')),
                ('distribution_strategy', models.CharField(choices=[('round_robin', 'Round Robin'), ('random', 'Random'), ('priority', 'Priority Order'), ('all_ring', 'Ring All'), ('least_recent', 'Least Recently Called')], default='round_robin', help_text='How calls are distributed among group members', max_length=20, verbose_name='Distribution Strategy')),
                ('ring_timeout', models.PositiveIntegerField(default=30, help_text='How long to ring each member before trying next', verbose_name='Ring Timeout (seconds)')),
                ('max_queue_size', models.PositiveIntegerField(default=10, help_text='Maximum number of callers in queue', verbose_name='Max Queue Size')),
                ('queue_timeout', models.PositiveIntegerField(default=300, help_text='Maximum time caller waits in queue', verbose_name='Queue Timeout (seconds)')),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('members', models.ManyToManyField(blank=True, related_name='groups', to='voip.internalnumber', verbose_name='Group Members')),
                ('server', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='number_groups', to='voip.sipserver', verbose_name='SIP Server')),
            ],
            options={
                'verbose_name': 'Number Group',
                'verbose_name_plural': 'Number Groups',
            },
        ),
        migrations.CreateModel(
            name='CallRoutingRule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Rule Name')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('priority', models.PositiveIntegerField(default=100, help_text='Lower number = higher priority', verbose_name='Priority')),
                ('caller_id_pattern', models.CharField(blank=True, help_text='Regex pattern for caller ID (e.g., ^\\+7, ^8800)', max_length=100, verbose_name='Caller ID Pattern')),
                ('called_number_pattern', models.CharField(blank=True, help_text='Regex pattern for called number', max_length=100, verbose_name='Called Number Pattern')),
                ('time_condition', models.CharField(blank=True, help_text='Time condition (e.g., weekdays 09:00-18:00)', max_length=200, verbose_name='Time Condition')),
                ('action', models.CharField(choices=[('route_to_number', 'Route to Number'), ('route_to_group', 'Route to Group'), ('route_to_queue', 'Route to Queue'), ('route_to_voicemail', 'Route to Voicemail'), ('play_announcement', 'Play Announcement'), ('hangup', 'Hangup'), ('forward_external', 'Forward to External Number')], max_length=20, verbose_name='Action')),
                ('target_external', models.CharField(blank=True, help_text='External number for forwarding', max_length=50, verbose_name='External Number')),
                ('announcement_text', models.TextField(blank=True, help_text='Text to play as announcement', verbose_name='Announcement Text')),
                ('active', models.BooleanField(default=True, verbose_name='Active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('target_group', models.ForeignKey(blank=True, help_text='Target group for routing', null=True, on_delete=django.db.models.deletion.CASCADE, to='voip.numbergroup', verbose_name='Target Group')),
                ('target_number', models.ForeignKey(blank=True, help_text='Target internal number for routing', null=True, on_delete=django.db.models.deletion.CASCADE, to='voip.internalnumber', verbose_name='Target Number')),
            ],
            options={
                'verbose_name': 'Call Routing Rule',
                'verbose_name_plural': 'Call Routing Rules',
                'ordering': ['priority'],
            },
        ),
        migrations.CreateModel(
            name='CallQueue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('caller_id', models.CharField(max_length=50, verbose_name='Caller ID')),
                ('called_number', models.CharField(max_length=50, verbose_name='Called Number')),
                ('queue_position', models.PositiveIntegerField(verbose_name='Queue Position')),
                ('wait_start_time', models.DateTimeField(auto_now_add=True, verbose_name='Wait Start Time')),
                ('estimated_wait_time', models.PositiveIntegerField(blank=True, null=True, verbose_name='Estimated Wait Time (seconds)')),
                ('status', models.CharField(choices=[('waiting', 'Waiting'), ('connecting', 'Connecting'), ('connected', 'Connected'), ('abandoned', 'Abandoned'), ('timeout', 'Timeout')], default='waiting', max_length=20, verbose_name='Status')),
                ('session_id', models.CharField(blank=True, help_text='SIP session identifier', max_length=100, verbose_name='Session ID')),
                ('group', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='call_queue', to='voip.numbergroup', verbose_name='Number Group')),
            ],
            options={
                'verbose_name': 'Call Queue',
                'verbose_name_plural': 'Call Queues',
            },
        ),
        migrations.CreateModel(
            name='CallLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(max_length=100, unique=True, verbose_name='Session ID')),
                ('caller_id', models.CharField(max_length=50, verbose_name='Caller ID')),
                ('called_number', models.CharField(max_length=50, verbose_name='Called Number')),
                ('direction', models.CharField(choices=[('inbound', 'Inbound'), ('outbound', 'Outbound'), ('internal', 'Internal')], max_length=10, verbose_name='Direction')),
                ('start_time', models.DateTimeField(verbose_name='Call Start Time')),
                ('answer_time', models.DateTimeField(blank=True, null=True, verbose_name='Answer Time')),
                ('end_time', models.DateTimeField(blank=True, null=True, verbose_name='Call End Time')),
                ('status', models.CharField(choices=[('ringing', 'Ringing'), ('answered', 'Answered'), ('busy', 'Busy'), ('no_answer', 'No Answer'), ('failed', 'Failed'), ('abandoned', 'Abandoned')], default='ringing', max_length=20, verbose_name='Call Status')),
                ('duration', models.PositiveIntegerField(blank=True, null=True, verbose_name='Duration (seconds)')),
                ('queue_wait_time', models.PositiveIntegerField(blank=True, null=True, verbose_name='Queue Wait Time (seconds)')),
                ('user_agent', models.CharField(blank=True, max_length=200, verbose_name='User Agent')),
                ('codec', models.CharField(blank=True, max_length=50, verbose_name='Audio Codec')),
                ('recording_file', models.CharField(blank=True, max_length=500, verbose_name='Recording File Path')),
                ('notes', models.TextField(blank=True, verbose_name='Notes')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('routed_to_group', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='group_calls', to='voip.numbergroup', verbose_name='Routed to Group')),
                ('routed_to_number', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='received_calls', to='voip.internalnumber', verbose_name='Routed to Number')),
                ('routing_rule', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='applied_calls', to='voip.callroutingrule', verbose_name='Applied Routing Rule')),
            ],
            options={
                'verbose_name': 'Call Log',
                'verbose_name_plural': 'Call Logs',
                'ordering': ['-start_time'],
            },
        ),
    ]