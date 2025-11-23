"""
Команда для управления маршрутизацией звонков и очередями
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from voip.models import (
    NumberGroup, CallRoutingRule, CallQueue, CallLog, 
    InternalNumber, SipServer
)
from voip.utils.routing import call_statistics, queue_manager
import re


class Command(BaseCommand):
    help = 'Управление маршрутизацией звонков и очередями'

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            dest='action', 
            help='Доступные действия'
        )
        
        # Создание группы номеров
        create_group = subparsers.add_parser(
            'create-group', 
            help='Создать группу номеров'
        )
        create_group.add_argument('--name', required=True, help='Название группы')
        create_group.add_argument('--description', help='Описание группы')
        create_group.add_argument('--strategy', 
                                choices=['round_robin', 'random', 'priority', 'all_ring', 'least_recent'],
                                default='round_robin',
                                help='Стратегия распределения')
        create_group.add_argument('--members', nargs='+', help='Список внутренних номеров')
        create_group.add_argument('--server-id', type=int, help='ID SIP сервера')
        
        # Создание правила маршрутизации
        create_rule = subparsers.add_parser(
            'create-rule',
            help='Создать правило маршрутизации'
        )
        create_rule.add_argument('--name', required=True, help='Название правила')
        create_rule.add_argument('--priority', type=int, default=100, help='Приоритет')
        create_rule.add_argument('--caller-pattern', help='Паттерн номера звонящего (regex)')
        create_rule.add_argument('--called-pattern', help='Паттерн вызываемого номера (regex)')
        create_rule.add_argument('--action', required=True,
                               choices=['route_to_number', 'route_to_group', 'forward_external', 
                                      'play_announcement', 'hangup'],
                               help='Действие')
        create_rule.add_argument('--target', help='Цель (номер, группа, внешний номер)')
        create_rule.add_argument('--announcement', help='Текст объявления')
        
        # Статистика
        stats = subparsers.add_parser('stats', help='Показать статистику')
        stats.add_argument('--group-id', type=int, help='ID группы для статистики')
        stats.add_argument('--days', type=int, default=7, help='Период в днях')
        
        # Управление очередями
        queue = subparsers.add_parser('queue', help='Управление очередями')
        queue.add_argument('--list', action='store_true', help='Показать текущие очереди')
        queue.add_argument('--clear', action='store_true', help='Очистить все очереди')
        queue.add_argument('--group-id', type=int, help='ID группы для операций с очередью')
        
        # Тестирование правил
        test = subparsers.add_parser('test', help='Тестировать правила маршрутизации')
        test.add_argument('--caller-id', required=True, help='Номер звонящего')
        test.add_argument('--called-number', required=True, help='Вызываемый номер')
        
        # Список объектов
        list_cmd = subparsers.add_parser('list', help='Показать списки объектов')
        list_cmd.add_argument('--groups', action='store_true', help='Список групп')
        list_cmd.add_argument('--rules', action='store_true', help='Список правил')
        list_cmd.add_argument('--numbers', action='store_true', help='Список номеров')

    def handle(self, *args, **options):
        action = options['action']
        
        if action == 'create-group':
            self._create_group(options)
        elif action == 'create-rule':
            self._create_rule(options)
        elif action == 'stats':
            self._show_statistics(options)
        elif action == 'queue':
            self._manage_queue(options)
        elif action == 'test':
            self._test_routing(options)
        elif action == 'list':
            self._list_objects(options)
        else:
            self.stdout.write(
                self.style.ERROR('Укажите действие: create-group, create-rule, stats, queue, test, list')
            )

    def _create_group(self, options):
        """Создать группу номеров"""
        self.stdout.write('📞 Создание группы номеров...')
        
        # Получаем сервер
        server_id = options.get('server_id')
        if server_id:
            try:
                server = SipServer.objects.get(id=server_id)
            except SipServer.DoesNotExist:
                raise CommandError(f'Сервер с ID {server_id} не найден')
        else:
            server = SipServer.objects.filter(active=True).first()
            if not server:
                raise CommandError('Нет активных SIP серверов')
        
        # Создаем группу
        group = NumberGroup.objects.create(
            name=options['name'],
            description=options.get('description', ''),
            server=server,
            distribution_strategy=options['strategy']
        )
        
        # Добавляем участников
        if options.get('members'):
            for number_str in options['members']:
                try:
                    internal_number = InternalNumber.objects.get(
                        number=number_str,
                        server=server,
                        active=True
                    )
                    group.members.add(internal_number)
                except InternalNumber.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'Номер {number_str} не найден')
                    )
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Создана группа: {group.name} (ID: {group.id})')
        )
        
        if group.members.exists():
            self.stdout.write(f'   Участников: {group.members.count()}')

    def _create_rule(self, options):
        """Создать правило маршрутизации"""
        self.stdout.write('🔀 Создание правила маршрутизации...')
        
        rule = CallRoutingRule.objects.create(
            name=options['name'],
            priority=options['priority'],
            caller_id_pattern=options.get('caller_pattern', ''),
            called_number_pattern=options.get('called_pattern', ''),
            action=options['action']
        )
        
        # Настраиваем цель в зависимости от действия
        target = options.get('target')
        if target:
            if options['action'] == 'route_to_number':
                try:
                    internal_number = InternalNumber.objects.get(
                        number=target, 
                        active=True
                    )
                    rule.target_number = internal_number
                except InternalNumber.DoesNotExist:
                    raise CommandError(f'Номер {target} не найден')
            
            elif options['action'] == 'route_to_group':
                try:
                    group = NumberGroup.objects.get(
                        name=target,
                        active=True
                    )
                    rule.target_group = group
                except NumberGroup.DoesNotExist:
                    raise CommandError(f'Группа {target} не найдена')
            
            elif options['action'] == 'forward_external':
                rule.target_external = target
        
        if options.get('announcement'):
            rule.announcement_text = options['announcement']
        
        rule.save()
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ Создано правило: {rule.name} (Приоритет: {rule.priority})')
        )

    def _show_statistics(self, options):
        """Показать статистику"""
        self.stdout.write('📊 Статистика звонков:')
        
        days = options['days']
        group_id = options.get('group_id')
        
        if group_id:
            try:
                group = NumberGroup.objects.get(id=group_id)
                stats = call_statistics.get_group_statistics(group, days)
                
                self.stdout.write(f'\n📱 Группа: {group.name}')
                self.stdout.write(f'   Период: {days} дней')
                self.stdout.write(f'   Всего звонков: {stats["total_calls"]}')
                self.stdout.write(f'   Отвеченных: {stats["answered_calls"]}')
                self.stdout.write(f'   Пропущенных: {stats["missed_calls"]}')
                self.stdout.write(f'   Процент ответов: {stats["answer_rate"]}%')
                self.stdout.write(f'   Среднее время ожидания: {stats["avg_wait_time"]}с')
                self.stdout.write(f'   Средняя длительность: {stats["avg_call_duration"]}с')
                
            except NumberGroup.DoesNotExist:
                raise CommandError(f'Группа с ID {group_id} не найдена')
        else:
            # Общая статистика
            from django.utils import timezone
            from datetime import timedelta
            
            start_date = timezone.now() - timedelta(days=days)
            total_calls = CallLog.objects.filter(start_time__gte=start_date).count()
            answered = CallLog.objects.filter(
                start_time__gte=start_date, 
                status='answered'
            ).count()
            
            self.stdout.write(f'\n🌍 Общая статистика за {days} дней:')
            self.stdout.write(f'   Всего звонков: {total_calls}')
            self.stdout.write(f'   Отвеченных: {answered}')
            if total_calls > 0:
                answer_rate = round((answered / total_calls) * 100, 1)
                self.stdout.write(f'   Процент ответов: {answer_rate}%')

    def _manage_queue(self, options):
        """Управление очередями"""
        if options.get('list'):
            self.stdout.write('📋 Текущие очереди:')
            
            queues = CallQueue.objects.filter(status='waiting').select_related('group')
            if not queues.exists():
                self.stdout.write('   Очереди пусты')
            else:
                for queue_entry in queues:
                    self.stdout.write(
                        f'   {queue_entry.group.name}: {queue_entry.caller_id} '
                        f'(поз. {queue_entry.queue_position}, ожидание {queue_entry.wait_time}с)'
                    )
        
        elif options.get('clear'):
            cleared = CallQueue.objects.filter(status='waiting').update(status='abandoned')
            self.stdout.write(
                self.style.SUCCESS(f'✅ Очищено очередей: {cleared}')
            )

    def _test_routing(self, options):
        """Тестировать правила маршрутизации"""
        caller_id = options['caller_id']
        called_number = options['called_number']
        
        self.stdout.write(f'🧪 Тестирование маршрутизации: {caller_id} -> {called_number}')
        
        # Импортируем функцию маршрутизации
        from voip.utils.routing import route_call
        
        result = route_call(caller_id, called_number, f"test_{int(timezone.now().timestamp())}")
        
        self.stdout.write(f'\nРезультат:')
        self.stdout.write(f'   Действие: {result["action"]}')
        
        if result['action'] == 'route':
            self.stdout.write(f'   Тип цели: {result.get("target_type", "N/A")}')
            self.stdout.write(f'   Цель: {result.get("target", "N/A")}')
            if result.get('group'):
                self.stdout.write(f'   Группа: {result["group"]}')
        elif result['action'] == 'error':
            self.stdout.write(
                self.style.ERROR(f'   Ошибка: {result.get("message", "Unknown")}')
            )
        elif result['action'] == 'not_found':
            self.stdout.write(
                self.style.WARNING('   Правила маршрутизации не найдены')
            )

    def _list_objects(self, options):
        """Показать списки объектов"""
        if options.get('groups'):
            self.stdout.write('📱 Группы номеров:')
            groups = NumberGroup.objects.filter(active=True)
            for group in groups:
                members_count = group.members.count()
                available_count = group.get_available_members().count()
                self.stdout.write(
                    f'   {group.id}: {group.name} '
                    f'({available_count}/{members_count} доступно, {group.distribution_strategy})'
                )
        
        elif options.get('rules'):
            self.stdout.write('🔀 Правила маршрутизации:')
            rules = CallRoutingRule.objects.filter(active=True).order_by('priority')
            for rule in rules:
                target_info = ''
                if rule.target_number:
                    target_info = f' -> номер {rule.target_number.number}'
                elif rule.target_group:
                    target_info = f' -> группа {rule.target_group.name}'
                elif rule.target_external:
                    target_info = f' -> внешний {rule.target_external}'
                
                self.stdout.write(
                    f'   {rule.priority}: {rule.name} ({rule.action}){target_info}'
                )
        
        elif options.get('numbers'):
            self.stdout.write('📞 Внутренние номера:')
            numbers = InternalNumber.objects.filter(active=True).select_related('user')
            for number in numbers:
                user_info = f' ({number.user.get_full_name()})' if number.user else ' (не назначен)'
                groups_info = ''
                if number.groups.exists():
                    group_names = ', '.join(number.groups.values_list('name', flat=True))
                    groups_info = f' [группы: {group_names}]'
                
                self.stdout.write(f'   {number.number}@{number.server.host}{user_info}{groups_info}')
        
        else:
            self.stdout.write('Укажите что показать: --groups, --rules или --numbers')