"""
Утилиты для маршрутизации входящих звонков и управления очередями
"""
import logging
import re
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from voip.models import (
    CallRoutingRule, NumberGroup, CallQueue, CallLog, 
    InternalNumber, SipAccount
)

logger = logging.getLogger(__name__)


class CallRouter:
    """Основной класс для маршрутизации звонков"""
    
    def __init__(self):
        self.logger = logger
    
    def route_incoming_call(self, caller_id, called_number, session_id=None):
        """
        Основная функция маршрутизации входящего звонка
        
        Args:
            caller_id: Номер звонящего
            called_number: Вызываемый номер
            session_id: ID сессии SIP
            
        Returns:
            dict: Результат маршрутизации с действием и параметрами
        """
        self.logger.info(f"Маршрутизация звонка: {caller_id} -> {called_number}")
        
        # Создаем запись в логе звонков
        call_log = self._create_call_log(
            caller_id=caller_id,
            called_number=called_number,
            session_id=session_id or f"call_{int(datetime.now().timestamp())}"
        )
        
        try:
            # Получаем правила маршрутизации по приоритету
            routing_rules = CallRoutingRule.objects.filter(
                active=True
            ).order_by('priority')
            
            for rule in routing_rules:
                if rule.matches_call(caller_id, called_number, timezone.now()):
                    self.logger.info(f"Применяется правило: {rule.name}")
                    
                    # Выполняем действие правила
                    result = rule.execute_action({
                        'caller_id': caller_id,
                        'called_number': called_number,
                        'session_id': call_log.session_id
                    })
                    
                    # Обновляем лог
                    call_log.routing_rule = rule
                    if result.get('target_type') == 'number':
                        call_log.routed_to_number = self._get_internal_number_by_number(result.get('target'))
                    elif result.get('target_type') == 'group_member':
                        call_log.routed_to_number = self._get_internal_number_by_number(result.get('target'))
                        call_log.routed_to_group = rule.target_group
                    
                    call_log.save()
                    result['call_log_id'] = call_log.id
                    
                    return result
            
            # Если не найдено правил, попробуем прямую маршрутизацию
            direct_result = self._try_direct_routing(called_number)
            if direct_result:
                call_log.routed_to_number = self._get_internal_number_by_number(called_number)
                call_log.save()
                direct_result['call_log_id'] = call_log.id
                return direct_result
            
            # Если ничего не найдено
            self.logger.warning(f"Не найдено правил маршрутизации для {called_number}")
            call_log.status = 'failed'
            call_log.notes = "No routing rules matched"
            call_log.save()
            
            return {
                'action': 'not_found',
                'message': 'No routing rules matched this call',
                'call_log_id': call_log.id
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка маршрутизации: {e}")
            call_log.status = 'failed'
            call_log.notes = f"Routing error: {str(e)}"
            call_log.save()
            
            return {
                'action': 'error',
                'message': str(e),
                'call_log_id': call_log.id
            }
    
    def _create_call_log(self, caller_id, called_number, session_id):
        """Создать запись в логе звонков"""
        return CallLog.objects.create(
            session_id=session_id,
            caller_id=caller_id,
            called_number=called_number,
            direction='inbound',
            start_time=timezone.now(),
            status='ringing'
        )
    
    def _get_internal_number_by_number(self, number):
        """Получить объект InternalNumber по номеру"""
        try:
            return InternalNumber.objects.get(number=number, active=True)
        except InternalNumber.DoesNotExist:
            return None
    
    def _try_direct_routing(self, called_number):
        """Попробовать прямую маршрутизацию на внутренний номер"""
        internal_number = self._get_internal_number_by_number(called_number)
        
        if internal_number and internal_number.user and hasattr(internal_number.user, 'sip_account'):
            sip_account = internal_number.user.sip_account
            if sip_account.active:
                return {
                    'action': 'route',
                    'target_type': 'direct',
                    'target': internal_number.number,
                    'sip_uri': internal_number.sip_uri
                }
        
        return None
    
    def update_call_status(self, call_log_id, status, answer_time=None, end_time=None):
        """Обновить статус звонка"""
        try:
            call_log = CallLog.objects.get(id=call_log_id)
            call_log.status = status
            
            if answer_time:
                call_log.answer_time = answer_time
            if end_time:
                call_log.end_time = end_time
                
            call_log.calculate_statistics()
            
            self.logger.info(f"Обновлен статус звонка {call_log.session_id}: {status}")
            
        except CallLog.DoesNotExist:
            self.logger.error(f"Не найден лог звонка с ID {call_log_id}")


class QueueManager:
    """Управление очередями звонков"""
    
    def __init__(self):
        self.logger = logger
    
    def add_to_queue(self, group, caller_id, called_number, session_id):
        """
        Добавить звонящего в очередь группы
        
        Returns:
            dict: Информация о позиции в очереди
        """
        # Проверяем размер очереди
        current_queue_size = CallQueue.objects.filter(
            group=group, 
            status='waiting'
        ).count()
        
        if current_queue_size >= group.max_queue_size:
            return {
                'status': 'queue_full',
                'message': f'Queue is full (max {group.max_queue_size})'
            }
        
        # Добавляем в очередь
        queue_position = current_queue_size + 1
        
        queue_entry = CallQueue.objects.create(
            group=group,
            caller_id=caller_id,
            called_number=called_number,
            queue_position=queue_position,
            session_id=session_id,
            estimated_wait_time=self._estimate_wait_time(group, queue_position)
        )
        
        self.logger.info(
            f"Добавлен в очередь {group.name}: {caller_id}, позиция {queue_position}"
        )
        
        return {
            'status': 'queued',
            'position': queue_position,
            'estimated_wait': queue_entry.estimated_wait_time,
            'queue_entry_id': queue_entry.id
        }
    
    def process_queue(self, group):
        """
        Обработать очередь группы - попытаться соединить ожидающих
        
        Returns:
            list: Список результатов обработки
        """
        results = []
        
        # Получаем ожидающих в очереди
        waiting_calls = CallQueue.objects.filter(
            group=group,
            status='waiting'
        ).order_by('wait_start_time')
        
        for queue_entry in waiting_calls:
            # Проверяем таймаут
            if queue_entry.wait_time > group.queue_timeout:
                queue_entry.status = 'timeout'
                queue_entry.save()
                results.append({
                    'session_id': queue_entry.session_id,
                    'action': 'timeout',
                    'reason': 'Queue timeout exceeded'
                })
                continue
            
            # Пытаемся найти доступного члена группы
            available_member = group.get_next_member()
            
            if available_member:
                # Пытаемся соединить
                queue_entry.status = 'connecting'
                queue_entry.save()
                
                results.append({
                    'session_id': queue_entry.session_id,
                    'action': 'connect',
                    'target': available_member.number,
                    'sip_uri': available_member.sip_uri,
                    'queue_entry_id': queue_entry.id
                })
            
        return results
    
    def remove_from_queue(self, queue_entry_id, status='connected'):
        """Удалить звонящего из очереди"""
        try:
            queue_entry = CallQueue.objects.get(id=queue_entry_id)
            queue_entry.status = status
            queue_entry.save()
            
            # Обновляем позиции остальных в очереди
            self._update_queue_positions(queue_entry.group)
            
            self.logger.info(f"Удален из очереди: {queue_entry.session_id} ({status})")
            
        except CallQueue.DoesNotExist:
            self.logger.error(f"Не найдена запись очереди с ID {queue_entry_id}")
    
    def _estimate_wait_time(self, group, position):
        """Оценить время ожидания в очереди"""
        # Простая оценка: позиция * среднее время обслуживания
        avg_call_duration = self._get_average_call_duration(group)
        return position * avg_call_duration
    
    def _get_average_call_duration(self, group):
        """Получить среднее время звонка для группы"""
        recent_calls = CallLog.objects.filter(
            routed_to_group=group,
            status='answered',
            start_time__gte=timezone.now() - timedelta(days=7)
        )
        
        if recent_calls.exists():
            avg_duration = recent_calls.aggregate(
                avg=models.Avg('duration')
            )['avg']
            return int(avg_duration) if avg_duration else 180  # 3 минуты по умолчанию
        
        return 180  # 3 минуты по умолчанию
    
    def _update_queue_positions(self, group):
        """Обновить позиции в очереди после удаления"""
        waiting_calls = CallQueue.objects.filter(
            group=group,
            status='waiting'
        ).order_by('wait_start_time')
        
        for i, queue_entry in enumerate(waiting_calls, 1):
            queue_entry.queue_position = i
            queue_entry.save()


class CallStatistics:
    """Статистика звонков"""
    
    def __init__(self):
        self.logger = logger
    
    def get_group_statistics(self, group, days=7):
        """Получить статистику по группе"""
        start_date = timezone.now() - timedelta(days=days)
        
        calls = CallLog.objects.filter(
            routed_to_group=group,
            start_time__gte=start_date
        )
        
        stats = {
            'total_calls': calls.count(),
            'answered_calls': calls.filter(status='answered').count(),
            'missed_calls': calls.filter(status='no_answer').count(),
            'abandoned_calls': calls.filter(status='abandoned').count(),
            'avg_wait_time': 0,
            'avg_call_duration': 0,
            'answer_rate': 0
        }
        
        if stats['total_calls'] > 0:
            # Средние показатели
            answered_calls = calls.filter(status='answered')
            if answered_calls.exists():
                from django.db.models import Avg
                avg_duration = answered_calls.aggregate(avg=Avg('duration'))['avg']
                stats['avg_call_duration'] = int(avg_duration) if avg_duration else 0
                
                avg_wait = answered_calls.filter(queue_wait_time__isnull=False).aggregate(
                    avg=Avg('queue_wait_time')
                )['avg']
                stats['avg_wait_time'] = int(avg_wait) if avg_wait else 0
            
            # Процент ответов
            stats['answer_rate'] = round(
                (stats['answered_calls'] / stats['total_calls']) * 100, 1
            )
        
        return stats
    
    def get_member_statistics(self, internal_number, days=7):
        """Получить статистику по члену группы"""
        start_date = timezone.now() - timedelta(days=days)
        
        calls = CallLog.objects.filter(
            routed_to_number=internal_number,
            start_time__gte=start_date
        )
        
        return {
            'total_calls': calls.count(),
            'answered_calls': calls.filter(status='answered').count(),
            'missed_calls': calls.filter(status='no_answer').count(),
            'avg_call_duration': calls.filter(
                status='answered'
            ).aggregate(
                avg=models.Avg('duration')
            )['avg'] or 0
        }


# Глобальные экземпляры для использования
call_router = CallRouter()
queue_manager = QueueManager()
call_statistics = CallStatistics()


# Удобные функции для импорта
def route_call(caller_id, called_number, session_id=None):
    """Маршрутизировать входящий звонок"""
    return call_router.route_incoming_call(caller_id, called_number, session_id)

def update_call_status(call_log_id, status, answer_time=None, end_time=None):
    """Обновить статус звонка"""
    return call_router.update_call_status(call_log_id, status, answer_time, end_time)

def add_to_queue(group, caller_id, called_number, session_id):
    """Добавить в очередь"""
    return queue_manager.add_to_queue(group, caller_id, called_number, session_id)

def process_group_queue(group):
    """Обработать очередь группы"""
    return queue_manager.process_queue(group)