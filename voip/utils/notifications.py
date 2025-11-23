"""
Система уведомлений для VoIP событий
Обработка пропущенных звонков, переполнения очередей и других критических событий
"""
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from voip.models import (
    CallLog, CallQueue, NumberGroup, InternalNumber, 
    SipAccount, CallRoutingRule
)

logger = logging.getLogger(__name__)
User = get_user_model()


class VoIPNotificationService:
    """Основной сервис уведомлений VoIP"""
    
    def __init__(self):
        self.logger = logger
        self.email_enabled = getattr(settings, 'VOIP_EMAIL_NOTIFICATIONS', True)
        self.webhook_enabled = getattr(settings, 'VOIP_WEBHOOK_NOTIFICATIONS', False)
        self.webhook_url = getattr(settings, 'VOIP_WEBHOOK_URL', None)
    
    def notify_missed_call(self, call_log):
        """
        Уведомление о пропущенном звонке
        
        Args:
            call_log: Объект CallLog с информацией о звонке
        """
        if call_log.status not in ['no_answer', 'busy']:
            return
        
        self.logger.info(f"Обработка пропущенного звонка: {call_log.session_id}")
        
        # Определяем получателей уведомления
        recipients = self._get_missed_call_recipients(call_log)
        
        if not recipients:
            self.logger.warning(f"Нет получателей для уведомления о пропущенном звонке {call_log.session_id}")
            return
        
        # Данные для уведомления
        notification_data = {
            'type': 'missed_call',
            'call_log': call_log,
            'caller_id': call_log.caller_id,
            'called_number': call_log.called_number,
            'timestamp': call_log.start_time,
            'duration': call_log.total_duration,
            'group': call_log.routed_to_group.name if call_log.routed_to_group else None,
            'routing_rule': call_log.routing_rule.name if call_log.routing_rule else None
        }
        
        # Отправляем уведомления
        self._send_email_notification(recipients, notification_data)
        self._send_webhook_notification(notification_data)
        
        # Логируем в CRM если есть интеграция
        self._create_crm_task_for_missed_call(call_log)
    
    def notify_queue_overflow(self, group, current_queue_size):
        """
        Уведомление о переполнении очереди
        
        Args:
            group: Группа номеров
            current_queue_size: Текущий размер очереди
        """
        if current_queue_size < group.max_queue_size * 0.9:  # 90% заполненности
            return
        
        self.logger.warning(f"Очередь группы {group.name} переполнена: {current_queue_size}/{group.max_queue_size}")
        
        # Получаем администраторов и менеджеров группы
        recipients = self._get_queue_overflow_recipients(group)
        
        notification_data = {
            'type': 'queue_overflow',
            'group': group,
            'current_size': current_queue_size,
            'max_size': group.max_queue_size,
            'utilization': round((current_queue_size / group.max_queue_size) * 100, 1),
            'timestamp': timezone.now(),
            'waiting_callers': self._get_waiting_callers(group)
        }
        
        self._send_email_notification(recipients, notification_data)
        self._send_webhook_notification(notification_data)
    
    def notify_agent_unavailable(self, group, unavailable_count):
        """
        Уведомление о недоступности агентов
        
        Args:
            group: Группа номеров
            unavailable_count: Количество недоступных агентов
        """
        total_agents = group.members.count()
        available_agents = group.get_available_members().count()
        
        if available_agents == 0 and total_agents > 0:
            self.logger.critical(f"Все агенты группы {group.name} недоступны!")
            
            recipients = self._get_agent_unavailable_recipients(group)
            
            notification_data = {
                'type': 'agents_unavailable',
                'group': group,
                'total_agents': total_agents,
                'available_agents': available_agents,
                'unavailable_agents': unavailable_count,
                'timestamp': timezone.now()
            }
            
            self._send_email_notification(recipients, notification_data)
            self._send_webhook_notification(notification_data)
    
    def notify_long_wait_time(self, queue_entry):
        """
        Уведомление о длительном ожидании в очереди
        
        Args:
            queue_entry: Запись в очереди CallQueue
        """
        wait_threshold = getattr(settings, 'VOIP_LONG_WAIT_THRESHOLD', 300)  # 5 минут
        
        if queue_entry.wait_time < wait_threshold:
            return
        
        self.logger.warning(f"Долгое ожидание в очереди: {queue_entry.caller_id} ждет {queue_entry.wait_time}с")
        
        recipients = self._get_long_wait_recipients(queue_entry.group)
        
        notification_data = {
            'type': 'long_wait_time',
            'queue_entry': queue_entry,
            'caller_id': queue_entry.caller_id,
            'wait_time': queue_entry.wait_time,
            'position': queue_entry.queue_position,
            'group': queue_entry.group,
            'timestamp': timezone.now()
        }
        
        self._send_email_notification(recipients, notification_data)
    
    def notify_system_health_issues(self):
        """
        Уведомление о проблемах со здоровьем системы
        """
        issues = self._check_system_health()
        
        if not issues:
            return
        
        self.logger.warning(f"Обнаружены проблемы системы: {len(issues)} проблем")
        
        recipients = self._get_system_admin_recipients()
        
        notification_data = {
            'type': 'system_health',
            'issues': issues,
            'timestamp': timezone.now(),
            'severity': self._calculate_severity(issues)
        }
        
        self._send_email_notification(recipients, notification_data)
        self._send_webhook_notification(notification_data)
    
    def send_daily_report(self):
        """
        Отправка ежедневного отчета
        """
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # Собираем статистику за вчера
        report_data = self._generate_daily_report(yesterday)
        
        recipients = self._get_daily_report_recipients()
        
        notification_data = {
            'type': 'daily_report',
            'date': yesterday,
            'report': report_data,
            'timestamp': timezone.now()
        }
        
        self._send_email_notification(recipients, notification_data)
    
    def _get_missed_call_recipients(self, call_log):
        """Получить получателей для уведомлений о пропущенных звонках"""
        recipients = []
        
        # Агент, которому был направлен звонок
        if call_log.routed_to_number and call_log.routed_to_number.user:
            user = call_log.routed_to_number.user
            if user.email and hasattr(user, 'sip_account'):
                if user.sip_account.voicemail_enabled:
                    recipients.append({
                        'user': user,
                        'email': user.sip_account.voicemail_email or user.email,
                        'role': 'agent'
                    })
        
        # Менеджеры группы (если звонок был направлен в группу)
        if call_log.routed_to_group:
            group_managers = self._get_group_managers(call_log.routed_to_group)
            recipients.extend(group_managers)
        
        return recipients
    
    def _get_queue_overflow_recipients(self, group):
        """Получить получателей для уведомлений о переполнении очереди"""
        recipients = []
        
        # Менеджеры группы
        recipients.extend(self._get_group_managers(group))
        
        # Системные администраторы
        recipients.extend(self._get_system_admin_recipients())
        
        return recipients
    
    def _get_agent_unavailable_recipients(self, group):
        """Получить получателей для уведомлений о недоступности агентов"""
        return self._get_queue_overflow_recipients(group)
    
    def _get_long_wait_recipients(self, group):
        """Получить получателей для уведомлений о долгом ожидании"""
        return self._get_group_managers(group)
    
    def _get_group_managers(self, group):
        """Получить менеджеров группы"""
        # Упрощенная логика - в реальности нужно добавить поле managers в NumberGroup
        # Пока возвращаем администраторов системы
        return self._get_system_admin_recipients()
    
    def _get_system_admin_recipients(self):
        """Получить системных администраторов"""
        admin_users = User.objects.filter(
            Q(is_superuser=True) | Q(groups__name='VoIP Administrators'),
            is_active=True,
            email__isnull=False
        ).exclude(email='')
        
        return [
            {
                'user': user,
                'email': user.email,
                'role': 'admin'
            }
            for user in admin_users
        ]
    
    def _get_daily_report_recipients(self):
        """Получить получателей ежедневного отчета"""
        # Менеджеры и администраторы
        report_users = User.objects.filter(
            Q(is_superuser=True) | 
            Q(groups__name__in=['VoIP Administrators', 'Call Center Managers']),
            is_active=True,
            email__isnull=False
        ).exclude(email='')
        
        return [
            {
                'user': user,
                'email': user.email,
                'role': 'manager'
            }
            for user in report_users
        ]
    
    def _get_waiting_callers(self, group):
        """Получить информацию об ожидающих звонящих"""
        waiting_calls = CallQueue.objects.filter(
            group=group,
            status='waiting'
        ).order_by('queue_position')
        
        return [
            {
                'caller_id': call.caller_id,
                'position': call.queue_position,
                'wait_time': call.wait_time
            }
            for call in waiting_calls
        ]
    
    def _check_system_health(self):
        """Проверить здоровье системы"""
        issues = []
        
        # Проверка неактивных SIP аккаунтов
        inactive_accounts = SipAccount.objects.filter(
            active=False,
            user__is_active=True
        ).count()
        
        if inactive_accounts > 0:
            issues.append({
                'type': 'inactive_accounts',
                'count': inactive_accounts,
                'description': f'{inactive_accounts} SIP аккаунтов неактивны',
                'severity': 'warning'
            })
        
        # Проверка правил маршрутизации без цели
        misconfigured_rules = CallRoutingRule.objects.filter(
            active=True,
            target_number__isnull=True,
            target_group__isnull=True,
            target_external__exact=''
        ).count()
        
        if misconfigured_rules > 0:
            issues.append({
                'type': 'misconfigured_rules',
                'count': misconfigured_rules,
                'description': f'{misconfigured_rules} правил маршрутизации неправильно настроены',
                'severity': 'error'
            })
        
        # Проверка пустых групп
        empty_groups = NumberGroup.objects.filter(
            active=True,
            members__isnull=True
        ).count()
        
        if empty_groups > 0:
            issues.append({
                'type': 'empty_groups',
                'count': empty_groups,
                'description': f'{empty_groups} групп не имеют участников',
                'severity': 'warning'
            })
        
        # Проверка высокого процента пропущенных звонков
        yesterday = timezone.now() - timedelta(days=1)
        total_calls = CallLog.objects.filter(start_time__gte=yesterday).count()
        missed_calls = CallLog.objects.filter(
            start_time__gte=yesterday,
            status='no_answer'
        ).count()
        
        if total_calls > 0:
            miss_rate = (missed_calls / total_calls) * 100
            if miss_rate > 30:  # Более 30% пропущенных звонков
                issues.append({
                    'type': 'high_miss_rate',
                    'value': round(miss_rate, 1),
                    'description': f'Высокий процент пропущенных звонков: {miss_rate:.1f}%',
                    'severity': 'critical'
                })
        
        return issues
    
    def _calculate_severity(self, issues):
        """Вычислить общую серьезность проблем"""
        if any(issue['severity'] == 'critical' for issue in issues):
            return 'critical'
        elif any(issue['severity'] == 'error' for issue in issues):
            return 'error'
        elif any(issue['severity'] == 'warning' for issue in issues):
            return 'warning'
        else:
            return 'info'
    
    def _generate_daily_report(self, date):
        """Сгенерировать ежедневный отчет"""
        start_of_day = timezone.make_aware(datetime.combine(date, datetime.min.time()))
        end_of_day = start_of_day + timedelta(days=1)
        
        calls = CallLog.objects.filter(
            start_time__gte=start_of_day,
            start_time__lt=end_of_day
        )
        
        # Общая статистика
        total_calls = calls.count()
        answered_calls = calls.filter(status='answered').count()
        missed_calls = calls.filter(status='no_answer').count()
        busy_calls = calls.filter(status='busy').count()
        
        # Статистика по группам
        group_stats = []
        for group in NumberGroup.objects.filter(active=True):
            group_calls = calls.filter(routed_to_group=group)
            group_total = group_calls.count()
            group_answered = group_calls.filter(status='answered').count()
            
            if group_total > 0:
                group_stats.append({
                    'name': group.name,
                    'total_calls': group_total,
                    'answered_calls': group_answered,
                    'answer_rate': round((group_answered / group_total) * 100, 1)
                })
        
        # Топ пропущенных номеров
        missed_numbers = calls.filter(status='no_answer').values(
            'called_number'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        return {
            'total_calls': total_calls,
            'answered_calls': answered_calls,
            'missed_calls': missed_calls,
            'busy_calls': busy_calls,
            'answer_rate': round((answered_calls / total_calls) * 100, 1) if total_calls > 0 else 0,
            'group_stats': group_stats,
            'top_missed_numbers': list(missed_numbers)
        }
    
    def _send_email_notification(self, recipients, data):
        """Отправить email уведомление"""
        if not self.email_enabled or not recipients:
            return
        
        try:
            # Выбираем шаблон в зависимости от типа уведомления
            template_map = {
                'missed_call': 'voip/notifications/missed_call_email.html',
                'queue_overflow': 'voip/notifications/queue_overflow_email.html',
                'agents_unavailable': 'voip/notifications/agents_unavailable_email.html',
                'long_wait_time': 'voip/notifications/long_wait_email.html',
                'system_health': 'voip/notifications/system_health_email.html',
                'daily_report': 'voip/notifications/daily_report_email.html'
            }
            
            template_name = template_map.get(data['type'], 'voip/notifications/default_email.html')
            
            # Формируем тему письма
            subject_map = {
                'missed_call': f'Пропущенный звонок от {data["caller_id"]}',
                'queue_overflow': f'Переполнение очереди группы {data["group"].name}',
                'agents_unavailable': f'Агенты группы {data["group"].name} недоступны',
                'long_wait_time': f'Долгое ожидание в очереди: {data["caller_id"]}',
                'system_health': 'Проблемы системы VoIP',
                'daily_report': f'Ежедневный отчет VoIP за {data["date"]}'
            }
            
            subject = subject_map.get(data['type'], 'VoIP уведомление')
            
            # Отправляем каждому получателю
            for recipient in recipients:
                try:
                    html_content = render_to_string(template_name, {
                        'recipient': recipient,
                        'data': data,
                        'timestamp': timezone.now()
                    })
                    
                    email = EmailMultiAlternatives(
                        subject=subject,
                        body=f"VoIP уведомление: {data['type']}",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        to=[recipient['email']]
                    )
                    
                    email.attach_alternative(html_content, "text/html")
                    email.send()
                    
                    self.logger.info(f"Email уведомление отправлено: {recipient['email']}")
                    
                except Exception as e:
                    self.logger.error(f"Ошибка отправки email {recipient['email']}: {e}")
        
        except Exception as e:
            self.logger.error(f"Ошибка отправки email уведомлений: {e}")
    
    def _send_webhook_notification(self, data):
        """Отправить webhook уведомление"""
        if not self.webhook_enabled or not self.webhook_url:
            return
        
        try:
            import requests
            
            payload = {
                'type': data['type'],
                'timestamp': data['timestamp'].isoformat(),
                'data': self._serialize_notification_data(data)
            }
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                self.logger.info(f"Webhook уведомление отправлено: {data['type']}")
            else:
                self.logger.warning(f"Webhook ответил кодом {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"Ошибка отправки webhook: {e}")
    
    def _serialize_notification_data(self, data):
        """Сериализовать данные для webhook"""
        # Упрощенная сериализация для webhook
        serialized = {}
        
        for key, value in data.items():
            if hasattr(value, 'isoformat'):  # datetime objects
                serialized[key] = value.isoformat()
            elif hasattr(value, 'id'):  # Django model objects
                serialized[key] = {
                    'id': value.id,
                    'name': str(value)
                }
            elif isinstance(value, (str, int, float, bool, list, dict)):
                serialized[key] = value
            else:
                serialized[key] = str(value)
        
        return serialized
    
    def _create_crm_task_for_missed_call(self, call_log):
        """Создать задачу в CRM для пропущенного звонка"""
        try:
            # Попытка создать задачу в модуле tasks
            from tasks.models import Task
            
            # Ищем контакт в CRM по номеру телефона
            contact = self._find_contact_by_phone(call_log.caller_id)
            
            task_description = f"""
            Пропущенный звонок от {call_log.caller_id}
            
            Время звонка: {call_log.start_time}
            Вызываемый номер: {call_log.called_number}
            Группа: {call_log.routed_to_group.name if call_log.routed_to_group else 'Не определена'}
            
            Необходимо связаться с клиентом.
            """
            
            Task.objects.create(
                title=f"Пропущенный звонок от {call_log.caller_id}",
                description=task_description.strip(),
                contact=contact,
                priority='high',
                task_type='callback',
                created_by_id=1  # Системный пользователь
            )
            
            self.logger.info(f"Создана задача для пропущенного звонка {call_log.session_id}")
            
        except ImportError:
            self.logger.debug("Модуль tasks не найден, пропуск создания задачи")
        except Exception as e:
            self.logger.error(f"Ошибка создания задачи для пропущенного звонка: {e}")
    
    def _find_contact_by_phone(self, phone_number):
        """Найти контакт в CRM по номеру телефона"""
        try:
            from crm.models import Contact
            
            # Очищаем номер от лишних символов
            clean_phone = ''.join(filter(str.isdigit, phone_number))
            
            # Ищем контакт по различным вариантам номера
            contact = Contact.objects.filter(
                Q(phone__contains=clean_phone[-10:]) |  # Последние 10 цифр
                Q(mobile__contains=clean_phone[-10:]) |
                Q(phone__icontains=phone_number) |
                Q(mobile__icontains=phone_number)
            ).first()
            
            return contact
            
        except ImportError:
            return None
        except Exception as e:
            self.logger.error(f"Ошибка поиска контакта по телефону {phone_number}: {e}")
            return None


# Глобальный экземпляр сервиса
notification_service = VoIPNotificationService()


# Удобные функции для прямого использования
def notify_missed_call(call_log):
    """Уведомить о пропущенном звонке"""
    return notification_service.notify_missed_call(call_log)


def notify_queue_overflow(group, current_size):
    """Уведомить о переполнении очереди"""
    return notification_service.notify_queue_overflow(group, current_size)


def notify_agent_unavailable(group, unavailable_count):
    """Уведомить о недоступности агентов"""
    return notification_service.notify_agent_unavailable(group, unavailable_count)


def check_system_health():
    """Проверить здоровье системы"""
    return notification_service.notify_system_health_issues()


def send_daily_report():
    """Отправить ежедневный отчет"""
    return notification_service.send_daily_report()