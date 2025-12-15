"""
Asterisk Queue Management - управление очередями и агентами
"""
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


class AsteriskQueueMonitor:
    """
    Класс для мониторинга и управления очередями Asterisk.
    """
    
    def __init__(self, ami_client):
        """
        Args:
            ami_client: Экземпляр AmiClient для отправки команд
        """
        self.ami = ami_client
        self.queue_stats = {}
    
    def get_queue_status(self, queue_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получить статус очереди (или всех очередей).
        
        Args:
            queue_name: Имя очереди (None для всех очередей)
        
        Returns:
            Список словарей со статусом очередей
        """
        queues = []
        
        def collect_queue_data(responses):
            current_queue = None
            for resp in responses:
                event_type = resp.get('Event', '')
                
                if event_type == 'QueueParams':
                    current_queue = {
                        'queue': resp.get('Queue'),
                        'max': int(resp.get('Max', 0)),
                        'strategy': resp.get('Strategy'),
                        'calls': int(resp.get('Calls', 0)),
                        'holdtime': int(resp.get('Holdtime', 0)),
                        'talktime': int(resp.get('TalkTime', 0)),
                        'completed': int(resp.get('Completed', 0)),
                        'abandoned': int(resp.get('Abandoned', 0)),
                        'service_level': int(resp.get('ServiceLevel', 0)),
                        'service_level_perf': float(resp.get('ServicelevelPerf', 0)),
                        'weight': int(resp.get('Weight', 0)),
                        'members': [],
                        'callers': []
                    }
                    queues.append(current_queue)
                
                elif event_type == 'QueueMember' and current_queue:
                    member = {
                        'name': resp.get('Name'),
                        'location': resp.get('Location'),
                        'membership': resp.get('Membership'),
                        'penalty': int(resp.get('Penalty', 0)),
                        'calls_taken': int(resp.get('CallsTaken', 0)),
                        'last_call': int(resp.get('LastCall', 0)),
                        'in_call': int(resp.get('InCall', 0)),
                        'status': self._parse_member_status(int(resp.get('Status', 0))),
                        'paused': resp.get('Paused') == '1',
                        'paused_reason': resp.get('PausedReason', ''),
                        'wrapup_time': int(resp.get('Wrapuptime', 0)),
                    }
                    current_queue['members'].append(member)
                
                elif event_type == 'QueueEntry' and current_queue:
                    caller = {
                        'position': int(resp.get('Position', 0)),
                        'channel': resp.get('Channel'),
                        'caller_id_num': resp.get('CallerIDNum'),
                        'caller_id_name': resp.get('CallerIDName'),
                        'wait': int(resp.get('Wait', 0)),
                    }
                    current_queue['callers'].append(caller)
        
        try:
            action_params = {}
            if queue_name:
                action_params['Queue'] = queue_name
            
            self.ami.send_action('QueueStatus', callback=collect_queue_data, **action_params)
            
            # Ждем сбора данных
            import time
            time.sleep(0.5)
            
            return queues
        except Exception as e:
            logger.error(f"Failed to get queue status: {e}")
            return []
    
    def add_queue_member(
        self,
        queue: str,
        interface: str,
        member_name: Optional[str] = None,
        penalty: int = 0,
        paused: bool = False
    ) -> Dict[str, Any]:
        """
        Добавить агента в очередь.
        
        Args:
            queue: Имя очереди
            interface: Интерфейс агента (например, 'SIP/1001')
            member_name: Имя агента
            penalty: Штраф (приоритет)
            paused: Начать в режиме паузы
        
        Returns:
            Словарь с результатом операции
        """
        action_params = {
            'Queue': queue,
            'Interface': interface,
            'Penalty': str(penalty),
        }
        
        if member_name:
            action_params['MemberName'] = member_name
        
        if paused:
            action_params['Paused'] = 'true'
        
        try:
            response = self.ami.send_action_sync('QueueAdd', **action_params)
            logger.info(f"Add member {interface} to queue {queue}: {response.get('Response')}")
            return response
        except Exception as e:
            logger.error(f"Failed to add queue member: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def remove_queue_member(
        self,
        queue: str,
        interface: str
    ) -> Dict[str, Any]:
        """
        Удалить агента из очереди.
        
        Args:
            queue: Имя очереди
            interface: Интерфейс агента
        
        Returns:
            Словарь с результатом операции
        """
        try:
            response = self.ami.send_action_sync(
                'QueueRemove',
                Queue=queue,
                Interface=interface
            )
            logger.info(f"Remove member {interface} from queue {queue}: {response.get('Response')}")
            return response
        except Exception as e:
            logger.error(f"Failed to remove queue member: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def pause_queue_member(
        self,
        queue: str,
        interface: str,
        paused: bool = True,
        reason: str = ''
    ) -> Dict[str, Any]:
        """
        Поставить агента на паузу или снять с паузы.
        
        Args:
            queue: Имя очереди
            interface: Интерфейс агента
            paused: True для паузы, False для возобновления
            reason: Причина паузы
        
        Returns:
            Словарь с результатом операции
        """
        action_params = {
            'Queue': queue,
            'Interface': interface,
            'Paused': 'true' if paused else 'false',
        }
        
        if reason:
            action_params['Reason'] = reason
        
        try:
            response = self.ami.send_action_sync('QueuePause', **action_params)
            status = "paused" if paused else "unpaused"
            logger.info(f"Member {interface} in queue {queue} {status}: {response.get('Response')}")
            return response
        except Exception as e:
            logger.error(f"Failed to pause/unpause queue member: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def set_member_penalty(
        self,
        queue: str,
        interface: str,
        penalty: int
    ) -> Dict[str, Any]:
        """
        Установить штраф (приоритет) агента в очереди.
        
        Args:
            queue: Имя очереди
            interface: Интерфейс агента
            penalty: Значение штрафа (0-9999)
        
        Returns:
            Словарь с результатом операции
        """
        try:
            response = self.ami.send_action_sync(
                'QueuePenalty',
                Queue=queue,
                Interface=interface,
                Penalty=str(penalty)
            )
            logger.info(f"Set penalty {penalty} for member {interface} in queue {queue}")
            return response
        except Exception as e:
            logger.error(f"Failed to set member penalty: {e}")
            return {'Response': 'Error', 'Message': str(e)}
    
    def get_queue_summary(self, queue_name: str) -> Dict[str, Any]:
        """
        Получить сводную статистику по очереди.
        
        Args:
            queue_name: Имя очереди
        
        Returns:
            Словарь со статистикой
        """
        queues = self.get_queue_status(queue_name)
        
        if not queues:
            return {
                'error': 'Queue not found',
                'queue': queue_name
            }
        
        queue = queues[0]
        
        # Расчет дополнительных метрик
        available_agents = sum(1 for m in queue['members'] if not m['paused'] and m['status'] == 'available')
        busy_agents = sum(1 for m in queue['members'] if m['in_call'] > 0)
        paused_agents = sum(1 for m in queue['members'] if m['paused'])
        
        avg_wait_time = 0
        if queue['callers']:
            avg_wait_time = sum(c['wait'] for c in queue['callers']) / len(queue['callers'])
        
        return {
            'queue': queue_name,
            'calls_waiting': queue['calls'],
            'available_agents': available_agents,
            'busy_agents': busy_agents,
            'paused_agents': paused_agents,
            'total_agents': len(queue['members']),
            'avg_hold_time': queue['holdtime'],
            'avg_talk_time': queue['talktime'],
            'avg_wait_time': int(avg_wait_time),
            'completed_calls': queue['completed'],
            'abandoned_calls': queue['abandoned'],
            'service_level': queue['service_level'],
            'service_level_perf': queue['service_level_perf'],
            'longest_wait': max([c['wait'] for c in queue['callers']], default=0),
            'callers_in_queue': queue['callers'],
            'members': queue['members']
        }
    
    @staticmethod
    def _parse_member_status(status_code: int) -> str:
        """
        Преобразовать код статуса агента в текст.
        
        Args:
            status_code: Числовой код статуса
        
        Returns:
            Текстовое представление статуса
        """
        status_map = {
            0: 'unknown',
            1: 'available',
            2: 'in_use',
            3: 'busy',
            4: 'invalid',
            5: 'unavailable',
            6: 'ringing',
            7: 'on_hold',
            8: 'ringinuse',
        }
        return status_map.get(status_code, f'unknown_{status_code}')
    
    def reload_queue(self, queue_name: str) -> Dict[str, Any]:
        """
        Перезагрузить конфигурацию очереди.
        
        Args:
            queue_name: Имя очереди
        
        Returns:
            Словарь с результатом операции
        """
        try:
            response = self.ami.send_action_sync(
                'QueueReload',
                Queue=queue_name
            )
            logger.info(f"Reload queue {queue_name}: {response.get('Response')}")
            return response
        except Exception as e:
            logger.error(f"Failed to reload queue: {e}")
            return {'Response': 'Error', 'Message': str(e)}
