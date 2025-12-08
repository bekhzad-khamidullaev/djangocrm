"""
Django management command для просмотра статистики очередей Asterisk
"""
from django.core.management.base import BaseCommand

from voip.ami import AmiClient
from voip.utils import load_asterisk_config
from voip.integrations.asterisk_queue import AsteriskQueueMonitor


class Command(BaseCommand):
    help = "Display Asterisk queue statistics"

    def add_arguments(self, parser):
        parser.add_argument(
            '--queue',
            type=str,
            help='Show statistics for specific queue only',
        )
        parser.add_argument(
            '--watch',
            action='store_true',
            help='Continuously watch queue status (refresh every 5 seconds)',
        )
        parser.add_argument(
            '--summary',
            action='store_true',
            help='Show summary only',
        )

    def handle(self, *args, **options):
        # Загружаем конфигурацию
        config = load_asterisk_config()
        queue_name = options.get('queue')
        watch_mode = options['watch']
        summary_only = options['summary']

        try:
            client = AmiClient(config)
            client.connect()
            
            monitor = AsteriskQueueMonitor(client)
            
            if watch_mode:
                self._watch_queues(monitor, queue_name, summary_only)
            else:
                self._show_queues(monitor, queue_name, summary_only)
            
            client.close()
            
        except ConnectionError as e:
            self.stdout.write(self.style.ERROR(f"Connection failed: {e}"))
        except KeyboardInterrupt:
            self.stdout.write("\nStopped by user")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {e}"))
            import traceback
            if options.get('verbosity', 1) > 1:
                traceback.print_exc()

    def _watch_queues(self, monitor, queue_name, summary_only):
        """Непрерывно отображать статус очередей"""
        import time
        import os
        
        while True:
            # Очищаем экран (работает на Unix и Windows)
            os.system('cls' if os.name == 'nt' else 'clear')
            
            self._show_queues(monitor, queue_name, summary_only)
            
            self.stdout.write("")
            self.stdout.write("Press Ctrl+C to stop watching...")
            
            time.sleep(5)

    def _show_queues(self, monitor, queue_name, summary_only):
        """Показать статус очередей"""
        from datetime import datetime
        
        self.stdout.write(self.style.MIGRATE_HEADING("Asterisk Queue Statistics"))
        self.stdout.write(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write("")
        
        if queue_name:
            # Статистика для конкретной очереди
            summary = monitor.get_queue_summary(queue_name)
            
            if 'error' in summary:
                self.stdout.write(self.style.ERROR(f"Queue '{queue_name}' not found"))
                return
            
            self._display_queue_summary(summary, summary_only)
        else:
            # Статистика для всех очередей
            queues = monitor.get_queue_status()
            
            if not queues:
                self.stdout.write("No queues found")
                return
            
            for queue_data in queues:
                queue_name = queue_data.get('queue')
                summary = monitor.get_queue_summary(queue_name)
                self._display_queue_summary(summary, summary_only)
                self.stdout.write("")

    def _display_queue_summary(self, summary, summary_only):
        """Отобразить сводку по очереди"""
        queue_name = summary['queue']
        
        # Заголовок очереди
        self.stdout.write(self.style.SUCCESS(f"═══ {queue_name} ═══"))
        
        # Основные метрики
        calls_waiting = summary['calls_waiting']
        if calls_waiting > 0:
            calls_style = self.style.WARNING
        else:
            calls_style = self.style.SUCCESS
        
        self.stdout.write(f"Calls waiting: {calls_style(str(calls_waiting))}")
        self.stdout.write(f"Longest wait: {summary['longest_wait']}s")
        
        # Агенты
        available = summary['available_agents']
        busy = summary['busy_agents']
        paused = summary['paused_agents']
        total = summary['total_agents']
        
        self.stdout.write(f"Agents: {total} total")
        self.stdout.write(f"  Available: {self.style.SUCCESS(str(available))}")
        self.stdout.write(f"  Busy: {self.style.NOTICE(str(busy))}")
        
        if paused > 0:
            self.stdout.write(f"  Paused: {self.style.WARNING(str(paused))}")
        
        # Статистика звонков
        self.stdout.write(f"Completed: {summary['completed_calls']}")
        self.stdout.write(f"Abandoned: {summary['abandoned_calls']}")
        
        if summary['completed_calls'] > 0:
            abandon_rate = (summary['abandoned_calls'] / 
                          (summary['completed_calls'] + summary['abandoned_calls'])) * 100
            self.stdout.write(f"Abandon rate: {abandon_rate:.1f}%")
        
        # Время
        self.stdout.write(f"Avg hold time: {summary['avg_hold_time']}s")
        self.stdout.write(f"Avg talk time: {summary['avg_talk_time']}s")
        
        # SLA
        if summary['service_level'] > 0:
            sla_perf = summary['service_level_perf']
            if sla_perf >= 80:
                sla_style = self.style.SUCCESS
            elif sla_perf >= 60:
                sla_style = self.style.WARNING
            else:
                sla_style = self.style.ERROR
            
            self.stdout.write(f"Service Level: {sla_style(f'{sla_perf:.1f}%')} "
                            f"({summary['service_level']}s target)")
        
        # Детальная информация (если не summary_only)
        if not summary_only:
            # Ожидающие звонки
            callers = summary.get('callers_in_queue', [])
            if callers:
                self.stdout.write("")
                self.stdout.write("Waiting callers:")
                for caller in callers:
                    wait_time = caller.get('wait', 0)
                    if wait_time > 120:
                        wait_style = self.style.ERROR
                    elif wait_time > 60:
                        wait_style = self.style.WARNING
                    else:
                        wait_style = lambda x: x
                    
                    self.stdout.write(
                        f"  {caller.get('position', '?')}. {caller.get('caller_id_num', 'Unknown')} "
                        f"- waiting {wait_style(str(wait_time))}s"
                    )
            
            # Агенты
            members = summary.get('members', [])
            if members:
                self.stdout.write("")
                self.stdout.write("Members:")
                for member in members:
                    name = member.get('name', 'Unknown')
                    status = member.get('status', 'unknown')
                    paused = member.get('paused', False)
                    calls_taken = member.get('calls_taken', 0)
                    
                    if paused:
                        status_display = self.style.WARNING(f"{status} (PAUSED)")
                        reason = member.get('paused_reason', '')
                        if reason:
                            status_display += f" - {reason}"
                    elif status == 'available':
                        status_display = self.style.SUCCESS(status)
                    elif status in ['busy', 'in_use', 'ringing']:
                        status_display = self.style.NOTICE(status)
                    else:
                        status_display = status
                    
                    self.stdout.write(f"  • {name}: {status_display} (calls: {calls_taken})")
