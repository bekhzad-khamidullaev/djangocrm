"""
Asterisk Health Monitoring - проверка состояния и мониторинг Asterisk
"""
import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class AsteriskHealthCheck:
    """
    Класс для проверки состояния Asterisk и мониторинга его работы.
    """
    
    CACHE_PREFIX = 'asterisk_health'
    CACHE_TIMEOUT = 300  # 5 минут
    
    def __init__(self, ami_client):
        """
        Args:
            ami_client: Экземпляр AmiClient для отправки команд
        """
        self.ami = ami_client
    
    def check_connection(self) -> Dict[str, Any]:
        """
        Проверить соединение с Asterisk AMI.
        
        Returns:
            Словарь с результатом проверки
        """
        result = {
            'status': 'unknown',
            'connected': False,
            'timestamp': timezone.now().isoformat(),
            'response_time': None,
            'error': None
        }
        
        try:
            start_time = time.time()
            response = self.ami.send_action_sync('Ping', timeout=5.0)
            response_time = time.time() - start_time
            
            if response.get('Response') == 'Success':
                result['status'] = 'healthy'
                result['connected'] = True
                result['response_time'] = round(response_time * 1000, 2)  # в миллисекундах
            else:
                result['status'] = 'unhealthy'
                result['error'] = response.get('Message', 'Ping failed')
        
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            logger.error(f"AMI connection check failed: {e}")
        
        # Кэшируем результат
        cache.set(f'{self.CACHE_PREFIX}:connection', result, self.CACHE_TIMEOUT)
        
        return result
    
    def get_system_info(self) -> Dict[str, Any]:
        """
        Получить информацию о системе Asterisk.
        
        Returns:
            Словарь с информацией о системе
        """
        info = {
            'version': None,
            'uptime': None,
            'reload_time': None,
            'system': None,
            'calls_active': 0,
            'calls_processed': 0,
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            # Получаем версию и системную информацию
            core_settings = self.ami.send_action_sync('CoreSettings', timeout=5.0)
            if core_settings.get('Response') == 'Success':
                info['version'] = core_settings.get('AsteriskVersion')
                info['system'] = core_settings.get('SystemName')
            
            # Получаем статистику системы
            core_status = self.ami.send_action_sync('CoreStatus', timeout=5.0)
            if core_status.get('Response') == 'Success':
                info['uptime'] = core_status.get('CoreStartupTime')
                info['reload_time'] = core_status.get('CoreReloadTime')
                info['calls_active'] = int(core_status.get('CoreCurrentCalls', 0))
            
            # Кэшируем результат
            cache.set(f'{self.CACHE_PREFIX}:system_info', info, self.CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Failed to get system info: {e}")
            info['error'] = str(e)
        
        return info
    
    def check_channels_availability(self) -> Dict[str, Any]:
        """
        Проверить доступность каналов.
        
        Returns:
            Словарь с информацией о каналах
        """
        result = {
            'status': 'unknown',
            'total_channels': 0,
            'active_channels': 0,
            'sip_peers': {
                'total': 0,
                'online': 0,
                'offline': 0,
                'unmonitored': 0
            },
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            # Получаем активные каналы
            channels = []
            
            def collect_channels(responses):
                for resp in responses:
                    if resp.get('Event') == 'CoreShowChannel':
                        channels.append(resp)
            
            self.ami.send_action('CoreShowChannels', callback=collect_channels)
            time.sleep(0.5)  # Ждем сбора данных
            
            result['active_channels'] = len(channels)
            
            # Получаем SIP пиры
            sip_peers = []
            
            def collect_sip_peers(responses):
                for resp in responses:
                    if resp.get('Event') == 'PeerEntry':
                        sip_peers.append(resp)
            
            self.ami.send_action('SIPpeers', callback=collect_sip_peers)
            time.sleep(0.5)
            
            result['sip_peers']['total'] = len(sip_peers)
            
            for peer in sip_peers:
                status = peer.get('Status', '').lower()
                if 'ok' in status or 'reachable' in status:
                    result['sip_peers']['online'] += 1
                elif 'unreachable' in status or 'lagged' in status:
                    result['sip_peers']['offline'] += 1
                else:
                    result['sip_peers']['unmonitored'] += 1
            
            # Определяем общий статус
            if result['sip_peers']['total'] > 0:
                online_percent = (result['sip_peers']['online'] / result['sip_peers']['total']) * 100
                if online_percent >= 90:
                    result['status'] = 'healthy'
                elif online_percent >= 50:
                    result['status'] = 'degraded'
                else:
                    result['status'] = 'unhealthy'
            else:
                result['status'] = 'unknown'
            
            # Кэшируем результат
            cache.set(f'{self.CACHE_PREFIX}:channels', result, self.CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Failed to check channels: {e}")
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def check_queues_health(self) -> Dict[str, Any]:
        """
        Проверить состояние очередей.
        
        Returns:
            Словарь с информацией о очередях
        """
        result = {
            'status': 'unknown',
            'total_queues': 0,
            'queues_with_agents': 0,
            'queues_with_calls': 0,
            'total_waiting_calls': 0,
            'longest_wait': 0,
            'alerts': [],
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            from voip.integrations.asterisk_queue import AsteriskQueueMonitor
            
            monitor = AsteriskQueueMonitor(self.ami)
            queues = monitor.get_queue_status()
            
            result['total_queues'] = len(queues)
            
            for queue in queues:
                queue_name = queue.get('queue')
                available_agents = sum(1 for m in queue.get('members', []) 
                                      if not m.get('paused') and m.get('status') == 'available')
                
                if available_agents > 0:
                    result['queues_with_agents'] += 1
                
                calls = queue.get('calls', 0)
                if calls > 0:
                    result['queues_with_calls'] += 1
                    result['total_waiting_calls'] += calls
                    
                    # Проверяем время ожидания
                    for caller in queue.get('callers', []):
                        wait_time = caller.get('wait', 0)
                        if wait_time > result['longest_wait']:
                            result['longest_wait'] = wait_time
                        
                        # Алерт при долгом ожидании (более 2 минут)
                        if wait_time > 120:
                            result['alerts'].append({
                                'type': 'long_wait',
                                'queue': queue_name,
                                'wait_time': wait_time,
                                'caller': caller.get('caller_id_num')
                            })
                
                # Алерт если в очереди есть звонки но нет доступных агентов
                if calls > 0 and available_agents == 0:
                    result['alerts'].append({
                        'type': 'no_agents',
                        'queue': queue_name,
                        'waiting_calls': calls
                    })
            
            # Определяем общий статус
            if result['alerts']:
                result['status'] = 'unhealthy'
            elif result['total_waiting_calls'] > 0:
                result['status'] = 'busy'
            else:
                result['status'] = 'healthy'
            
            # Кэшируем результат
            cache.set(f'{self.CACHE_PREFIX}:queues', result, self.CACHE_TIMEOUT)
            
        except Exception as e:
            logger.error(f"Failed to check queues: {e}")
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
    
    def get_full_health_report(self) -> Dict[str, Any]:
        """
        Получить полный отчет о состоянии системы.
        
        Returns:
            Словарь с полным отчетом
        """
        report = {
            'overall_status': 'unknown',
            'timestamp': timezone.now().isoformat(),
            'checks': {}
        }
        
        # Проверка соединения
        connection = self.check_connection()
        report['checks']['connection'] = connection
        
        if not connection['connected']:
            report['overall_status'] = 'critical'
            report['message'] = 'Cannot connect to Asterisk AMI'
            return report
        
        # Системная информация
        system_info = self.get_system_info()
        report['checks']['system'] = system_info
        
        # Проверка каналов
        channels = self.check_channels_availability()
        report['checks']['channels'] = channels
        
        # Проверка очередей
        queues = self.check_queues_health()
        report['checks']['queues'] = queues
        
        # Определяем общий статус
        statuses = [
            connection['status'],
            channels['status'],
            queues['status']
        ]
        
        if 'error' in statuses or 'unhealthy' in statuses:
            report['overall_status'] = 'unhealthy'
        elif 'degraded' in statuses:
            report['overall_status'] = 'degraded'
        else:
            report['overall_status'] = 'healthy'
        
        return report
    
    def get_cached_health_report(self) -> Optional[Dict[str, Any]]:
        """
        Получить кэшированный отчет о состоянии (если доступен).
        
        Returns:
            Словарь с отчетом или None
        """
        return cache.get(f'{self.CACHE_PREFIX}:full_report')
    
    def monitor_call_quality(self, threshold_seconds: int = 300) -> Dict[str, Any]:
        """
        Мониторинг качества звонков (длительность, завершения).
        
        Args:
            threshold_seconds: Порог для анализа последних звонков
        
        Returns:
            Словарь со статистикой качества
        """
        result = {
            'status': 'unknown',
            'total_calls': 0,
            'completed_calls': 0,
            'failed_calls': 0,
            'avg_duration': 0,
            'short_calls': 0,  # Звонки короче 10 секунд
            'timestamp': timezone.now().isoformat()
        }
        
        try:
            # Получаем статистику из CallLog
            from crm.models.others import CallLog
            
            threshold_time = timezone.now() - timedelta(seconds=threshold_seconds)
            recent_calls = CallLog.objects.filter(
                created_date__gte=threshold_time,
                direction='inbound'
            )
            
            result['total_calls'] = recent_calls.count()
            
            if result['total_calls'] > 0:
                completed = recent_calls.filter(duration__gt=0)
                result['completed_calls'] = completed.count()
                result['failed_calls'] = result['total_calls'] - result['completed_calls']
                
                if completed.exists():
                    from django.db.models import Avg
                    avg_duration = completed.aggregate(Avg('duration'))['duration__avg']
                    result['avg_duration'] = round(avg_duration or 0, 2)
                
                result['short_calls'] = completed.filter(duration__lt=10).count()
                
                # Определяем статус
                completion_rate = (result['completed_calls'] / result['total_calls']) * 100
                if completion_rate >= 90:
                    result['status'] = 'excellent'
                elif completion_rate >= 70:
                    result['status'] = 'good'
                elif completion_rate >= 50:
                    result['status'] = 'fair'
                else:
                    result['status'] = 'poor'
        
        except Exception as e:
            logger.error(f"Failed to monitor call quality: {e}")
            result['status'] = 'error'
            result['error'] = str(e)
        
        return result
