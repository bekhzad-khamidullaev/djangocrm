"""
Фоновые задачи для VoIP системы
Обработка уведомлений, мониторинг и автоматизация
"""
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.management import call_command
from django.db.models import Count, Q, Avg
from celery import shared_task
from voip.models import (
    CallLog, CallQueue, NumberGroup, InternalNumber, 
    SipAccount, CallRoutingRule
)
from voip.utils.notifications import (
    notification_service, notify_missed_call, notify_queue_overflow,
    check_system_health, send_daily_report
)
from voip.utils.routing import queue_manager

logger = logging.getLogger(__name__)


@shared_task(name='voip.process_missed_calls')
def process_missed_calls():
    """
    Обработать пропущенные звонки за последние 15 минут
    """
    logger.info("Запуск обработки пропущенных звонков")
    
    # Получаем пропущенные звонки за последние 15 минут
    cutoff_time = timezone.now() - timedelta(minutes=15)
    
    missed_calls = CallLog.objects.filter(
        status__in=['no_answer', 'busy'],
        start_time__gte=cutoff_time,
        created_at__gte=cutoff_time  # Только недавно созданные записи
    ).select_related('routed_to_number__user', 'routed_to_group')
    
    processed_count = 0
    
    for call_log in missed_calls:
        try:
            # Проверяем, не обработан ли уже этот звонок
            if hasattr(call_log, '_notification_sent'):
                continue
            
            notify_missed_call(call_log)
            
            # Помечаем как обработанный (в реальности нужно добавить поле в модель)
            call_log._notification_sent = True
            processed_count += 1
            
        except Exception as e:
            logger.error(f"Ошибка обработки пропущенного звонка {call_log.id}: {e}")
    
    logger.info(f"Обработано пропущенных звонков: {processed_count}")
    return processed_count


@shared_task(name='voip.monitor_queue_health')
def monitor_queue_health():
    """
    Мониторинг здоровья очередей
    """
    logger.info("Запуск мониторинга очередей")
    
    issues_found = 0
    
    # Проверяем все активные группы
    for group in NumberGroup.objects.filter(active=True):
        try:
            # Текущий размер очереди
            current_queue_size = CallQueue.objects.filter(
                group=group,
                status='waiting'
            ).count()
            
            # Проверка переполнения
            utilization = (current_queue_size / group.max_queue_size) * 100
            if utilization >= 90:
                notify_queue_overflow(group, current_queue_size)
                issues_found += 1
                logger.warning(f"Переполнение очереди {group.name}: {utilization:.1f}%")
            
            # Проверка долгих ожиданий
            long_wait_threshold = getattr(settings, 'VOIP_LONG_WAIT_THRESHOLD', 300)
            long_waiting = CallQueue.objects.filter(
                group=group,
                status='waiting',
                wait_start_time__lte=timezone.now() - timedelta(seconds=long_wait_threshold)
            )
            
            for queue_entry in long_waiting:
                notification_service.notify_long_wait_time(queue_entry)
                issues_found += 1
            
            # Проверка доступности агентов
            available_agents = group.get_available_members().count()
            total_agents = group.members.count()
            
            if available_agents == 0 and total_agents > 0:
                notification_service.notify_agent_unavailable(group, total_agents)
                issues_found += 1
                logger.critical(f"Все агенты группы {group.name} недоступны")
        
        except Exception as e:
            logger.error(f"Ошибка мониторинга группы {group.name}: {e}")
            issues_found += 1
    
    logger.info(f"Мониторинг очередей завершен, найдено проблем: {issues_found}")
    return issues_found


@shared_task(name='voip.process_queue_timeouts')
def process_queue_timeouts():
    """
    Обработать истекшие тайм-ауты в очередях
    """
    logger.info("Обработка тайм-аутов очередей")
    
    processed_count = 0
    
    # Получаем записи с истекшим тайм-аутом
    for group in NumberGroup.objects.filter(active=True):
        timeout_threshold = timezone.now() - timedelta(seconds=group.queue_timeout)
        
        expired_entries = CallQueue.objects.filter(
            group=group,
            status='waiting',
            wait_start_time__lte=timeout_threshold
        )
        
        for entry in expired_entries:
            try:
                # Обновляем статус на timeout
                entry.status = 'timeout'
                entry.save()
                
                # Логируем в CallLog если есть
                try:
                    call_log = CallLog.objects.get(session_id=entry.session_id)
                    call_log.status = 'abandoned'
                    call_log.queue_wait_time = entry.wait_time
                    call_log.end_time = timezone.now()
                    call_log.save()
                except CallLog.DoesNotExist:
                    pass
                
                processed_count += 1
                logger.info(f"Тайм-аут очереди: {entry.caller_id} в группе {group.name}")
                
            except Exception as e:
                logger.error(f"Ошибка обработки тайм-аута {entry.id}: {e}")
    
    logger.info(f"Обработано тайм-аутов очередей: {processed_count}")
    return processed_count


@shared_task(name='voip.cleanup_old_queue_entries')
def cleanup_old_queue_entries():
    """
    Очистка старых записей очередей
    """
    logger.info("Очистка старых записей очередей")
    
    # Удаляем записи старше 24 часов
    cutoff_time = timezone.now() - timedelta(hours=24)
    
    deleted_count = CallQueue.objects.filter(
        wait_start_time__lt=cutoff_time,
        status__in=['connected', 'abandoned', 'timeout']
    ).delete()[0]
    
    logger.info(f"Удалено старых записей очередей: {deleted_count}")
    return deleted_count


@shared_task(name='voip.system_health_check')
def system_health_check():
    """
    Проверка здоровья системы VoIP
    """
    logger.info("Проверка здоровья системы VoIP")
    
    try:
        check_system_health()
        logger.info("Проверка здоровья системы завершена")
        return True
    except Exception as e:
        logger.error(f"Ошибка проверки здоровья системы: {e}")
        return False


@shared_task(name='voip.generate_daily_report')
def generate_daily_report():
    """
    Генерация и отправка ежедневного отчета
    """
    logger.info("Генерация ежедневного отчета")
    
    try:
        send_daily_report()
        logger.info("Ежедневный отчет отправлен")
        return True
    except Exception as e:
        logger.error(f"Ошибка генерации ежедневного отчета: {e}")
        return False


@shared_task(name='voip.optimize_queue_positions')
def optimize_queue_positions():
    """
    Оптимизация позиций в очередях
    """
    logger.info("Оптимизация позиций в очередях")
    
    optimized_count = 0
    
    for group in NumberGroup.objects.filter(active=True):
        try:
            # Получаем ожидающих в очереди
            waiting_entries = CallQueue.objects.filter(
                group=group,
                status='waiting'
            ).order_by('wait_start_time')
            
            # Переназначаем позиции
            for index, entry in enumerate(waiting_entries, 1):
                if entry.queue_position != index:
                    entry.queue_position = index
                    entry.save()
                    optimized_count += 1
        
        except Exception as e:
            logger.error(f"Ошибка оптимизации очереди {group.name}: {e}")
    
    logger.info(f"Оптимизировано позиций в очередях: {optimized_count}")
    return optimized_count


@shared_task(name='voip.update_call_statistics')
def update_call_statistics():
    """
    Обновление статистики звонков
    """
    logger.info("Обновление статистики звонков")
    
    updated_count = 0
    
    # Обновляем статистику для звонков без продолжительности
    calls_to_update = CallLog.objects.filter(
        duration__isnull=True,
        end_time__isnull=False,
        status='answered'
    )
    
    for call_log in calls_to_update:
        try:
            call_log.calculate_statistics()
            updated_count += 1
        except Exception as e:
            logger.error(f"Ошибка обновления статистики звонка {call_log.id}: {e}")
    
    logger.info(f"Обновлена статистика для {updated_count} звонков")
    return updated_count


@shared_task(name='voip.sync_sip_accounts')
def sync_sip_accounts():
    """
    Синхронизация SIP аккаунтов с пользователями
    """
    logger.info("Синхронизация SIP аккаунтов")
    
    from django.contrib.auth import get_user_model
    from voip.utils.sip_helpers import create_sip_account_for_user
    
    User = get_user_model()
    created_count = 0
    
    # Создаем SIP аккаунты для пользователей без них
    users_without_sip = User.objects.filter(
        sip_account__isnull=True,
        is_active=True
    )
    
    for user in users_without_sip:
        try:
            create_sip_account_for_user(user)
            created_count += 1
            logger.info(f"Создан SIP аккаунт для пользователя {user.username}")
        except Exception as e:
            logger.error(f"Ошибка создания SIP аккаунта для {user.username}: {e}")
    
    logger.info(f"Создано SIP аккаунтов: {created_count}")
    return created_count


@shared_task(name='voip.backup_call_logs')
def backup_call_logs():
    """
    Резервное копирование старых логов звонков
    """
    logger.info("Резервное копирование логов звонков")
    
    # Архивируем записи старше 90 дней
    cutoff_date = timezone.now() - timedelta(days=90)
    
    old_logs = CallLog.objects.filter(start_time__lt=cutoff_date)
    total_logs = old_logs.count()
    
    if total_logs == 0:
        logger.info("Нет логов для архивирования")
        return 0
    
    try:
        # В реальности здесь можно экспортировать в файл или другую БД
        # Пока просто логируем
        logger.info(f"К архивированию: {total_logs} логов звонков")
        
        # Можно добавить реальное архивирование:
        # export_call_logs_to_file(old_logs)
        # old_logs.delete()
        
        return total_logs
    
    except Exception as e:
        logger.error(f"Ошибка резервного копирования: {e}")
        return 0


@shared_task(name='voip.generate_analytics_cache')
def generate_analytics_cache():
    """
    Предварительная генерация кэша аналитики
    """
    logger.info("Генерация кэша аналитики")
    
    try:
        # Генерируем статистику для разных периодов
        periods = [1, 7, 30, 90]
        
        for days in periods:
            start_date = timezone.now() - timedelta(days=days)
            
            # Общая статистика
            total_calls = CallLog.objects.filter(start_time__gte=start_date).count()
            answered_calls = CallLog.objects.filter(
                start_time__gte=start_date,
                status='answered'
            ).count()
            
            # Статистика по группам
            for group in NumberGroup.objects.filter(active=True):
                group_calls = CallLog.objects.filter(
                    start_time__gte=start_date,
                    routed_to_group=group
                ).count()
                
                # Здесь можно кэшировать результаты в Redis или БД
                logger.debug(f"Группа {group.name} за {days} дней: {group_calls} звонков")
        
        logger.info("Генерация кэша аналитики завершена")
        return True
    
    except Exception as e:
        logger.error(f"Ошибка генерации кэша аналитики: {e}")
        return False


@shared_task(name='voip.check_inactive_numbers')
def check_inactive_numbers():
    """
    Проверка неактивных номеров
    """
    logger.info("Проверка неактивных номеров")
    
    issues_count = 0
    
    # Номера без пользователей
    unassigned_numbers = InternalNumber.objects.filter(
        user__isnull=True,
        active=True
    ).count()
    
    # Номера с неактивными SIP аккаунтами
    inactive_sip_numbers = InternalNumber.objects.filter(
        active=True,
        sip_account__active=False
    ).count()
    
    # Номера с неактивными пользователями
    inactive_user_numbers = InternalNumber.objects.filter(
        active=True,
        user__is_active=False
    ).count()
    
    total_issues = unassigned_numbers + inactive_sip_numbers + inactive_user_numbers
    
    if total_issues > 0:
        logger.warning(
            f"Найдено проблем с номерами: {unassigned_numbers} неназначенных, "
            f"{inactive_sip_numbers} с неактивными SIP, {inactive_user_numbers} с неактивными пользователями"
        )
    
    logger.info(f"Проверка номеров завершена, найдено проблем: {total_issues}")
    return total_issues


@shared_task(name='voip.process_webhook_queue')
def process_webhook_queue():
    """
    Обработка очереди webhook уведомлений
    """
    logger.info("Обработка очереди webhook")
    
    # Здесь можно реализовать обработку отложенных webhook'ов
    # если основной webhook недоступен
    
    processed_count = 0
    
    try:
        # Логика обработки отложенных webhook'ов
        logger.debug("Webhook очередь пуста")
        return processed_count
    
    except Exception as e:
        logger.error(f"Ошибка обработки webhook очереди: {e}")
        return 0


# Функции для запуска интеграций
@shared_task(name='voip.start_asterisk_integration')
def start_asterisk_integration_task():
    """
    Запуск интеграции с Asterisk в фоновом режиме
    """
    try:
        from voip.integrations.asterisk import start_asterisk_integration
        import asyncio
        
        asyncio.run(start_asterisk_integration())
        return True
    except Exception as e:
        logger.error(f"Ошибка запуска интеграции Asterisk: {e}")
        return False


@shared_task(name='voip.start_freeswitch_integration')
def start_freeswitch_integration_task():
    """
    Запуск интеграции с FreeSWITCH в фоновом режиме
    """
    try:
        from voip.integrations.freeswitch import start_freeswitch_integration
        import asyncio
        
        asyncio.run(start_freeswitch_integration())
        return True
    except Exception as e:
        logger.error(f"Ошибка запуска интеграции FreeSWITCH: {e}")
        return False


# Настройки периодических задач для Celery Beat
# Добавьте в settings.py:
"""
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'process-missed-calls': {
        'task': 'voip.process_missed_calls',
        'schedule': 60.0,  # Каждую минуту
    },
    'monitor-queue-health': {
        'task': 'voip.monitor_queue_health',
        'schedule': 30.0,  # Каждые 30 секунд
    },
    'process-queue-timeouts': {
        'task': 'voip.process_queue_timeouts',
        'schedule': 60.0,  # Каждую минуту
    },
    'cleanup-old-queue-entries': {
        'task': 'voip.cleanup_old_queue_entries',
        'schedule': crontab(hour=2, minute=0),  # В 02:00 каждый день
    },
    'system-health-check': {
        'task': 'voip.system_health_check',
        'schedule': crontab(minute='*/15'),  # Каждые 15 минут
    },
    'generate-daily-report': {
        'task': 'voip.generate_daily_report',
        'schedule': crontab(hour=9, minute=0),  # В 09:00 каждый день
    },
    'optimize-queue-positions': {
        'task': 'voip.optimize_queue_positions',
        'schedule': 300.0,  # Каждые 5 минут
    },
    'update-call-statistics': {
        'task': 'voip.update_call_statistics',
        'schedule': 600.0,  # Каждые 10 минут
    },
    'sync-sip-accounts': {
        'task': 'voip.sync_sip_accounts',
        'schedule': crontab(hour=1, minute=0),  # В 01:00 каждый день
    },
    'generate-analytics-cache': {
        'task': 'voip.generate_analytics_cache',
        'schedule': crontab(minute='*/30'),  # Каждые 30 минут
    },
    'check-inactive-numbers': {
        'task': 'voip.check_inactive_numbers',
        'schedule': crontab(hour=3, minute=0),  # В 03:00 каждый день
    },
    'process-cold-call-campaigns': {
        'task': 'voip.process_cold_call_campaigns',
        'schedule': 60.0,  # Every minute - check for scheduled calls
    },
}
"""


# ============================================================================
# COLD CALL CAMPAIGN TASKS
# ============================================================================

@shared_task(name='voip.initiate_cold_call', bind=True, max_retries=3)
def initiate_cold_call(self, call_id: int, from_number: str, to_number: str, campaign_id: int = None):
    """
    Initiate a cold call through VoIP provider
    
    Args:
        call_id: ColdCall model ID
        from_number: Caller ID to use
        to_number: Number to dial
        campaign_id: Optional campaign ID
    """
    from voip.models import CallLog
    from crm.models import Lead, Contact
    
    logger.info(f"Initiating cold call {call_id}: {from_number} -> {to_number}")
    
    try:
        # Import here to avoid circular imports
        from voip.utils.call_initiator import CallInitiator
        
        initiator = CallInitiator()
        result = initiator.make_call(
            from_number=from_number,
            to_number=to_number,
            call_id=call_id,
            campaign_id=campaign_id
        )
        
        if result['success']:
            logger.info(f"Cold call {call_id} initiated successfully. Session: {result.get('session_id')}")
            
            # Create call log
            CallLog.objects.create(
                session_id=result.get('session_id', f'cold-{call_id}'),
                caller_id=from_number,
                called_number=to_number,
                direction='outbound',
                start_time=timezone.now(),
                status='ringing',
                notes=f'Cold call campaign: {campaign_id}' if campaign_id else 'Cold call'
            )
            
            return {
                'success': True,
                'call_id': call_id,
                'session_id': result.get('session_id'),
                'message': 'Call initiated'
            }
        else:
            raise Exception(result.get('error', 'Unknown error'))
            
    except Exception as e:
        logger.error(f"Failed to initiate cold call {call_id}: {str(e)}")
        
        # Retry with exponential backoff
        try:
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for cold call {call_id}")
            return {
                'success': False,
                'call_id': call_id,
                'error': str(e)
            }


@shared_task(name='voip.schedule_cold_call')
def schedule_cold_call(lead_id: int = None, contact_id: int = None, 
                       phone_number: str = None, scheduled_time: str = None,
                       campaign_id: int = None, from_number: str = None):
    """
    Schedule a cold call for later execution
    
    Args:
        lead_id: Lead to call
        contact_id: Contact to call
        phone_number: Direct phone number
        scheduled_time: ISO format datetime string
        campaign_id: Campaign ID
        from_number: Caller ID to use
    """
    from voip.models import CallLog
    from crm.models import Lead, Contact
    
    # Determine target and phone number
    target_name = "Unknown"
    target_type = None
    target_id = None
    
    if lead_id:
        try:
            lead = Lead.objects.get(id=lead_id)
            phone_number = phone_number or lead.phone
            target_name = lead.first_name or "Lead"
            target_type = "lead"
            target_id = lead_id
        except Lead.DoesNotExist:
            logger.error(f"Lead {lead_id} not found")
            return {'success': False, 'error': 'Lead not found'}
    
    elif contact_id:
        try:
            contact = Contact.objects.get(id=contact_id)
            phone_number = phone_number or contact.phone
            target_name = contact.first_name or "Contact"
            target_type = "contact"
            target_id = contact_id
        except Contact.DoesNotExist:
            logger.error(f"Contact {contact_id} not found")
            return {'success': False, 'error': 'Contact not found'}
    
    if not phone_number:
        logger.error("No phone number provided")
        return {'success': False, 'error': 'No phone number'}
    
    # Get default caller ID if not provided
    if not from_number:
        from_number = getattr(settings, 'DEFAULT_CALLER_ID', '1000')
    
    # Parse scheduled time
    if scheduled_time:
        try:
            scheduled_dt = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
            
            # Schedule for future
            delay_seconds = (scheduled_dt - timezone.now()).total_seconds()
            
            if delay_seconds > 0:
                logger.info(f"Scheduling cold call to {phone_number} for {scheduled_dt}")
                # Use Celery's eta parameter
                initiate_cold_call.apply_async(
                    args=[0, from_number, phone_number, campaign_id],
                    eta=scheduled_dt
                )
                return {
                    'success': True,
                    'message': f'Call scheduled for {scheduled_dt}',
                    'scheduled_time': scheduled_dt.isoformat()
                }
        except ValueError as e:
            logger.error(f"Invalid scheduled_time format: {e}")
    
    # Execute immediately if no valid scheduled time
    logger.info(f"Initiating immediate cold call to {phone_number}")
    result = initiate_cold_call.delay(0, from_number, phone_number, campaign_id)
    
    return {
        'success': True,
        'message': 'Call initiated immediately',
        'task_id': result.id
    }


@shared_task(name='voip.process_cold_call_campaigns')
def process_cold_call_campaigns():
    """
    Process active cold call campaigns and schedule calls
    This task runs every minute to check for scheduled calls
    """
    from crm.models import Lead
    
    logger.info("Processing cold call campaigns")
    
    # Get leads that are scheduled for cold calls
    # This is a placeholder - you'd have a ColdCallCampaign model
    now = timezone.now()
    
    # Example: Get leads marked for cold calling
    leads_to_call = Lead.objects.filter(
        stage__name__icontains='cold call',
        phone__isnull=False
    ).exclude(phone='')[:10]  # Limit to prevent overload
    
    scheduled_count = 0
    
    for lead in leads_to_call:
        # Check if already called recently
        recent_call = CallLog.objects.filter(
            called_number=lead.phone,
            start_time__gte=now - timedelta(hours=24)
        ).exists()
        
        if not recent_call:
            schedule_cold_call.delay(
                lead_id=lead.id,
                phone_number=lead.phone
            )
            scheduled_count += 1
    
    logger.info(f"Scheduled {scheduled_count} cold calls")
    
    return {
        'success': True,
        'scheduled': scheduled_count
    }


@shared_task(name='voip.bulk_schedule_cold_calls')
def bulk_schedule_cold_calls(phone_numbers: list, campaign_id: int = None, 
                              from_number: str = None, delay_between_calls: int = 30):
    """
    Schedule multiple cold calls in bulk with delay between each
    
    Args:
        phone_numbers: List of phone numbers to call
        campaign_id: Campaign ID
        from_number: Caller ID to use
        delay_between_calls: Seconds between each call (default 30)
    """
    logger.info(f"Bulk scheduling {len(phone_numbers)} cold calls")
    
    if not from_number:
        from_number = getattr(settings, 'DEFAULT_CALLER_ID', '1000')
    
    scheduled_tasks = []
    
    for idx, phone in enumerate(phone_numbers):
        # Schedule with incremental delay
        eta = timezone.now() + timedelta(seconds=delay_between_calls * idx)
        
        task = initiate_cold_call.apply_async(
            args=[0, from_number, phone, campaign_id],
            eta=eta
        )
        
        scheduled_tasks.append({
            'phone': phone,
            'task_id': task.id,
            'scheduled_for': eta.isoformat()
        })
    
    logger.info(f"Scheduled {len(scheduled_tasks)} cold calls")
    
    return {
        'success': True,
        'total_scheduled': len(scheduled_tasks),
        'tasks': scheduled_tasks
    }


@shared_task(name='voip.cleanup_failed_cold_calls')
def cleanup_failed_cold_calls():
    """
    Clean up and retry failed cold calls
    """
    from voip.models import CallLog
    
    logger.info("Cleaning up failed cold calls")
    
    # Get failed calls from last 24 hours
    cutoff = timezone.now() - timedelta(hours=24)
    
    failed_calls = CallLog.objects.filter(
        status='failed',
        start_time__gte=cutoff,
        notes__icontains='cold call'
    )
    
    retry_count = 0
    
    for call in failed_calls:
        # Check if we should retry
        # This is simplified - you'd want more sophisticated retry logic
        if 'retry' not in call.notes.lower():
            logger.info(f"Retrying failed call to {call.called_number}")
            
            schedule_cold_call.delay(
                phone_number=call.called_number,
                from_number=call.caller_id
            )
            
            # Mark as retried
            call.notes += " [RETRY SCHEDULED]"
            call.save()
            
            retry_count += 1
    
    logger.info(f"Scheduled {retry_count} retry calls")
    
    return {
        'success': True,
        'retries_scheduled': retry_count
    }