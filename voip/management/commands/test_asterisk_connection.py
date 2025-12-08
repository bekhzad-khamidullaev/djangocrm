"""
Django management command для тестирования подключения к Asterisk
"""
from django.core.management.base import BaseCommand
from django.conf import settings

from voip.ami import AmiClient
from voip.utils import load_asterisk_config
from voip.utils.asterisk_health import AsteriskHealthCheck
from voip.integrations.asterisk_queue import AsteriskQueueMonitor


class Command(BaseCommand):
    help = "Test connection to Asterisk AMI and display system information"

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Run full health check including channels and queues',
        )
        parser.add_argument(
            '--queues',
            action='store_true',
            help='Show queue status',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Testing Asterisk AMI Connection"))
        self.stdout.write("")

        # Загружаем конфигурацию
        config = load_asterisk_config()
        
        self.stdout.write(f"Host: {config.get('HOST', 'Not configured')}")
        self.stdout.write(f"Port: {config.get('PORT', 'Not configured')}")
        self.stdout.write(f"Username: {config.get('USERNAME', 'Not configured')}")
        self.stdout.write(f"SSL: {config.get('USE_SSL', False)}")
        self.stdout.write("")

        # Пытаемся подключиться
        try:
            client = AmiClient(config)
            self.stdout.write("Connecting to Asterisk AMI...", ending='')
            client.connect()
            self.stdout.write(self.style.SUCCESS(" OK"))
            
            # Базовая проверка соединения
            health_check = AsteriskHealthCheck(client)
            
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Connection Test"))
            connection_result = health_check.check_connection()
            
            if connection_result['connected']:
                self.stdout.write(self.style.SUCCESS(f"✓ Connected (response time: {connection_result['response_time']}ms)"))
            else:
                self.stdout.write(self.style.ERROR(f"✗ Connection failed: {connection_result.get('error')}"))
                return
            
            # Системная информация
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("System Information"))
            system_info = health_check.get_system_info()
            
            self.stdout.write(f"Version: {system_info.get('version', 'Unknown')}")
            self.stdout.write(f"System: {system_info.get('system', 'Unknown')}")
            self.stdout.write(f"Active calls: {system_info.get('calls_active', 0)}")
            
            # Полная проверка
            if options['full']:
                self.stdout.write("")
                self.stdout.write(self.style.MIGRATE_HEADING("Full Health Check"))
                
                full_report = health_check.get_full_health_report()
                
                overall_status = full_report['overall_status']
                if overall_status == 'healthy':
                    status_style = self.style.SUCCESS
                elif overall_status == 'degraded':
                    status_style = self.style.WARNING
                else:
                    status_style = self.style.ERROR
                
                self.stdout.write(f"Overall Status: {status_style(overall_status.upper())}")
                
                # Каналы
                channels_info = full_report['checks'].get('channels', {})
                self.stdout.write("")
                self.stdout.write("Channels:")
                self.stdout.write(f"  Active: {channels_info.get('active_channels', 0)}")
                
                sip_peers = channels_info.get('sip_peers', {})
                self.stdout.write(f"  SIP Peers: {sip_peers.get('total', 0)} total")
                self.stdout.write(f"    Online: {sip_peers.get('online', 0)}")
                self.stdout.write(f"    Offline: {sip_peers.get('offline', 0)}")
                self.stdout.write(f"    Unmonitored: {sip_peers.get('unmonitored', 0)}")
                
                # Очереди
                queues_info = full_report['checks'].get('queues', {})
                self.stdout.write("")
                self.stdout.write("Queues:")
                self.stdout.write(f"  Total: {queues_info.get('total_queues', 0)}")
                self.stdout.write(f"  With agents: {queues_info.get('queues_with_agents', 0)}")
                self.stdout.write(f"  Waiting calls: {queues_info.get('total_waiting_calls', 0)}")
                
                if queues_info.get('longest_wait', 0) > 0:
                    self.stdout.write(f"  Longest wait: {queues_info['longest_wait']}s")
                
                # Алерты
                alerts = queues_info.get('alerts', [])
                if alerts:
                    self.stdout.write("")
                    self.stdout.write(self.style.WARNING("Alerts:"))
                    for alert in alerts:
                        alert_type = alert.get('type')
                        if alert_type == 'long_wait':
                            self.stdout.write(
                                f"  ⚠ Long wait in queue {alert['queue']}: "
                                f"{alert['wait_time']}s (caller: {alert.get('caller', 'unknown')})"
                            )
                        elif alert_type == 'no_agents':
                            self.stdout.write(
                                f"  ⚠ No agents in queue {alert['queue']} "
                                f"({alert['waiting_calls']} calls waiting)"
                            )
            
            # Статус очередей
            if options['queues']:
                self.stdout.write("")
                self.stdout.write(self.style.MIGRATE_HEADING("Queue Status"))
                
                monitor = AsteriskQueueMonitor(client)
                queues = monitor.get_queue_status()
                
                if not queues:
                    self.stdout.write("No queues found")
                else:
                    for queue in queues:
                        self.stdout.write("")
                        self.stdout.write(f"Queue: {self.style.SUCCESS(queue['queue'])}")
                        self.stdout.write(f"  Strategy: {queue.get('strategy', 'Unknown')}")
                        self.stdout.write(f"  Calls waiting: {queue.get('calls', 0)}")
                        self.stdout.write(f"  Completed: {queue.get('completed', 0)}")
                        self.stdout.write(f"  Abandoned: {queue.get('abandoned', 0)}")
                        self.stdout.write(f"  Avg hold time: {queue.get('holdtime', 0)}s")
                        self.stdout.write(f"  Avg talk time: {queue.get('talktime', 0)}s")
                        
                        members = queue.get('members', [])
                        self.stdout.write(f"  Members: {len(members)}")
                        
                        for member in members:
                            status = member.get('status', 'unknown')
                            paused = member.get('paused', False)
                            
                            if paused:
                                status_display = self.style.WARNING(f"{status} (PAUSED)")
                            elif status == 'available':
                                status_display = self.style.SUCCESS(status)
                            elif status in ['busy', 'in_use']:
                                status_display = self.style.NOTICE(status)
                            else:
                                status_display = status
                            
                            self.stdout.write(f"    - {member['name']}: {status_display}")
                            self.stdout.write(f"      Calls taken: {member.get('calls_taken', 0)}")
            
            # Закрываем соединение
            client.close()
            
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("Connection test completed successfully"))
            
        except ConnectionError as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Connection failed: {e}"))
            self.stdout.write("")
            self.stdout.write("Troubleshooting tips:")
            self.stdout.write("1. Check that Asterisk is running")
            self.stdout.write("2. Verify AMI is enabled in /etc/asterisk/manager.conf")
            self.stdout.write("3. Check firewall settings (default port 5038)")
            self.stdout.write("4. Verify credentials in settings")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n✗ Error: {e}"))
            import traceback
            if options.get('verbosity', 1) > 1:
                traceback.print_exc()
