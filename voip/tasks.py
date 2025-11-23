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
}
"""