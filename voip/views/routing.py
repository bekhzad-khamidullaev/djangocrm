"""
API views для обработки маршрутизации входящих звонков
"""
import json
import logging
from datetime import datetime
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from voip.utils.routing import (
    call_router, queue_manager, call_statistics, 
    route_call, update_call_status, add_to_queue
)
from voip.models import NumberGroup, CallLog, CallQueue


logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class IncomingCallView(View):
    """
    API для обработки входящих звонков
    POST /voip/incoming/
    """
    
    def post(self, request):
        """
        Обработать входящий звонок и вернуть инструкции маршрутизации
        
        Expected JSON payload:
        {
            "caller_id": "+79001234567",
            "called_number": "100",
            "session_id": "call_abc123",
            "user_agent": "SIP Client 1.0",
            "timestamp": "2023-12-01T10:30:00Z"
        }
        """
        try:
            data = json.loads(request.body.decode('utf-8'))
            
            caller_id = data.get('caller_id')
            called_number = data.get('called_number')
            session_id = data.get('session_id')
            
            if not caller_id or not called_number:
                return JsonResponse({
                    'error': 'Missing required fields: caller_id, called_number'
                }, status=400)
            
            logger.info(f"Входящий звонок: {caller_id} -> {called_number}")
            
            # Маршрутизируем звонок
            routing_result = route_call(
                caller_id=caller_id,
                called_number=called_number,
                session_id=session_id
            )
            
            # Дополняем результат метаданными
            routing_result.update({
                'timestamp': timezone.now().isoformat(),
                'caller_id': caller_id,
                'called_number': called_number,
                'session_id': session_id
            })
            
            logger.info(f"Результат маршрутизации: {routing_result['action']}")
            
            return JsonResponse(routing_result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON payload'
            }, status=400)
        except Exception as e:
            logger.error(f"Ошибка обработки входящего звонка: {e}")
            return JsonResponse({
                'error': f'Internal error: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch')
class CallStatusUpdateView(View):
    """
    API для обновления статуса звонка
    POST /voip/status/
    """
    
    def post(self, request):
        """
        Обновить статус звонка
        
        Expected JSON payload:
        {
            "session_id": "call_abc123",
            "status": "answered|no_answer|busy|failed|abandoned",
            "answer_time": "2023-12-01T10:30:15Z",
            "end_time": "2023-12-01T10:35:00Z",
            "codec": "PCMU",
            "user_agent": "SIP Phone 2.0"
        }
        """
        try:
            data = json.loads(request.body.decode('utf-8'))
            
            session_id = data.get('session_id')
            status = data.get('status')
            
            if not session_id or not status:
                return JsonResponse({
                    'error': 'Missing required fields: session_id, status'
                }, status=400)
            
            # Находим лог звонка
            try:
                call_log = CallLog.objects.get(session_id=session_id)
            except CallLog.DoesNotExist:
                return JsonResponse({
                    'error': f'Call log not found for session {session_id}'
                }, status=404)
            
            # Обновляем статус
            call_log.status = status
            
            # Обновляем временные метки
            if data.get('answer_time'):
                try:
                    answer_time_str = str(data['answer_time']).strip()
                    if answer_time_str:
                        call_log.answer_time = datetime.fromisoformat(
                            answer_time_str.replace('Z', '+00:00')
                        )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid answer_time format: {data.get('answer_time')}: {e}")
            
            if data.get('end_time'):
                try:
                    end_time_str = str(data['end_time']).strip()
                    if end_time_str:
                        call_log.end_time = datetime.fromisoformat(
                            end_time_str.replace('Z', '+00:00')
                        )
                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid end_time format: {data.get('end_time')}: {e}")
            
            # Дополнительная информация
            if data.get('codec'):
                call_log.codec = data['codec']
            if data.get('user_agent'):
                call_log.user_agent = data['user_agent']
            
            # Вычисляем статистику
            call_log.calculate_statistics()
            
            logger.info(f"Обновлен статус звонка {session_id}: {status}")
            
            return JsonResponse({
                'status': 'success',
                'session_id': session_id,
                'updated_status': status,
                'duration': call_log.duration
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON payload'
            }, status=400)
        except Exception as e:
            logger.error(f"Ошибка обновления статуса звонка: {e}")
            return JsonResponse({
                'error': f'Internal error: {str(e)}'
            }, status=500)


@method_decorator(csrf_exempt, name='dispatch') 
class QueueManagementView(View):
    """
    API для управления очередями звонков
    """
    
    def get(self, request, group_id=None):
        """
        Получить информацию об очередях
        GET /voip/queue/ - все очереди
        GET /voip/queue/{group_id}/ - конкретная группа
        """
        try:
            if group_id:
                try:
                    group = NumberGroup.objects.get(id=group_id, active=True)
                    queue_entries = CallQueue.objects.filter(
                        group=group, 
                        status='waiting'
                    ).order_by('queue_position')
                    
                    queue_data = {
                        'group_id': group.id,
                        'group_name': group.name,
                        'max_queue_size': group.max_queue_size,
                        'current_size': queue_entries.count(),
                        'entries': []
                    }
                    
                    for entry in queue_entries:
                        queue_data['entries'].append({
                            'id': entry.id,
                            'caller_id': entry.caller_id,
                            'position': entry.queue_position,
                            'wait_time': entry.wait_time,
                            'estimated_wait': entry.estimated_wait_time
                        })
                    
                    return JsonResponse(queue_data)
                    
                except NumberGroup.DoesNotExist:
                    return JsonResponse({
                        'error': f'Group {group_id} not found'
                    }, status=404)
            else:
                # Все очереди
                groups = NumberGroup.objects.filter(active=True)
                queues_data = []
                
                for group in groups:
                    waiting_count = CallQueue.objects.filter(
                        group=group, 
                        status='waiting'
                    ).count()
                    
                    queues_data.append({
                        'group_id': group.id,
                        'group_name': group.name,
                        'waiting_calls': waiting_count,
                        'max_queue_size': group.max_queue_size
                    })
                
                return JsonResponse({
                    'queues': queues_data,
                    'timestamp': timezone.now().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Ошибка получения информации об очередях: {e}")
            return JsonResponse({
                'error': f'Internal error: {str(e)}'
            }, status=500)
    
    def post(self, request):
        """
        Добавить звонящего в очередь
        
        Expected JSON payload:
        {
            "group_id": 1,
            "caller_id": "+79001234567",
            "called_number": "100",
            "session_id": "call_abc123"
        }
        """
        try:
            data = json.loads(request.body.decode('utf-8'))
            
            group_id = data.get('group_id')
            caller_id = data.get('caller_id')
            called_number = data.get('called_number')
            session_id = data.get('session_id')
            
            if not all([group_id, caller_id, called_number, session_id]):
                return JsonResponse({
                    'error': 'Missing required fields'
                }, status=400)
            
            try:
                group = NumberGroup.objects.get(id=group_id, active=True)
            except NumberGroup.DoesNotExist:
                return JsonResponse({
                    'error': f'Group {group_id} not found'
                }, status=404)
            
            # Добавляем в очередь
            queue_result = add_to_queue(
                group=group,
                caller_id=caller_id,
                called_number=called_number,
                session_id=session_id
            )
            
            return JsonResponse(queue_result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON payload'
            }, status=400)
        except Exception as e:
            logger.error(f"Ошибка добавления в очередь: {e}")
            return JsonResponse({
                'error': f'Internal error: {str(e)}'
            }, status=500)


class CallStatisticsView(View):
    """
    API для получения статистики звонков
    """
    
    def get(self, request):
        """
        Получить статистику звонков
        GET /voip/stats/?period=7&group_id=1
        """
        try:
            period_days = int(request.GET.get('period', 7))
            group_id = request.GET.get('group_id')
            
            if group_id:
                try:
                    group = NumberGroup.objects.get(id=group_id)
                    stats = call_statistics.get_group_statistics(group, period_days)
                    stats['group_name'] = group.name
                    stats['period_days'] = period_days
                    return JsonResponse(stats)
                except NumberGroup.DoesNotExist:
                    return JsonResponse({
                        'error': f'Group {group_id} not found'
                    }, status=404)
            else:
                # Общая статистика
                start_date = timezone.now() - timezone.timedelta(days=period_days)
                
                total_calls = CallLog.objects.filter(
                    start_time__gte=start_date
                ).count()
                
                answered_calls = CallLog.objects.filter(
                    start_time__gte=start_date,
                    status='answered'
                ).count()
                
                stats = {
                    'period_days': period_days,
                    'total_calls': total_calls,
                    'answered_calls': answered_calls,
                    'answer_rate': round((answered_calls / total_calls * 100), 1) if total_calls > 0 else 0,
                    'timestamp': timezone.now().isoformat()
                }
                
                return JsonResponse(stats)
                
        except ValueError:
            return JsonResponse({
                'error': 'Invalid period parameter'
            }, status=400)
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return JsonResponse({
                'error': f'Internal error: {str(e)}'
            }, status=500)


# Удобные функции для прямого использования
@csrf_exempt
@require_http_methods(["POST"])
def handle_incoming_call(request):
    """Простая функция для обработки входящих звонков"""
    view = IncomingCallView()
    return view.post(request)


@csrf_exempt
@require_http_methods(["POST"])
def update_call_status_api(request):
    """Простая функция для обновления статуса звонка"""
    view = CallStatusUpdateView()
    return view.post(request)


@require_http_methods(["GET"])
def get_queue_status(request, group_id=None):
    """Простая функция для получения статуса очереди"""
    view = QueueManagementView()
    return view.get(request, group_id)