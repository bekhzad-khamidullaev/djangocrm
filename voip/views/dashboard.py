"""
Views для дашборда аналитики звонков и мониторинга очередей
"""
import json
from datetime import datetime, timedelta
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from django.views import View
from django.utils import timezone
from django.db.models import Count, Avg, Max, Min, Q
from django.db.models.functions import TruncHour, TruncDay
from voip.models import (
    NumberGroup, CallLog, CallQueue, InternalNumber, 
    SipAccount, CallRoutingRule
)
from voip.utils.routing import call_statistics


class CallDashboardView(LoginRequiredMixin, TemplateView):
    """Главный дашборд аналитики звонков"""
    template_name = 'voip/call_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Базовая информация для инициализации
        context.update({
            'total_groups': NumberGroup.objects.filter(active=True).count(),
            'total_rules': CallRoutingRule.objects.filter(active=True).count(),
            'active_queues': CallQueue.objects.filter(status='waiting').count(),
        })
        
        return context


class QueueMonitorView(LoginRequiredMixin, TemplateView):
    """Монитор очередей в реальном времени"""
    template_name = 'voip/queue_monitor.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Информация о текущих очередях
        current_queues = CallQueue.objects.filter(
            status='waiting'
        ).select_related('group')
        
        context.update({
            'current_queue_count': current_queues.count(),
            'groups_with_queues': current_queues.values_list(
                'group__name', flat=True
            ).distinct().count(),
        })
        
        return context


class DashboardStatsAPIView(View):
    """API для получения статистики дашборда"""
    
    def get(self, request):
        """
        Получить статистику для дашборда
        
        Query params:
        - period: количество дней (по умолчанию 7)
        - group_id: ID группы для фильтрации (опционально)
        """
        period_days = int(request.GET.get('period', 7))
        group_id = request.GET.get('group_id')
        
        # Определяем период
        end_date = timezone.now()
        start_date = end_date - timedelta(days=period_days)
        previous_start_date = start_date - timedelta(days=period_days)
        
        # Базовый запрос
        calls_query = CallLog.objects.filter(
            start_time__gte=start_date,
            start_time__lte=end_date
        )
        
        previous_calls_query = CallLog.objects.filter(
            start_time__gte=previous_start_date,
            start_time__lt=start_date
        )
        
        # Фильтрация по группе
        if group_id:
            try:
                group = NumberGroup.objects.get(id=group_id)
                calls_query = calls_query.filter(routed_to_group=group)
                previous_calls_query = previous_calls_query.filter(routed_to_group=group)
            except NumberGroup.DoesNotExist:
                pass
        
        # Основная статистика
        stats = self._calculate_call_stats(calls_query)
        previous_stats = self._calculate_call_stats(previous_calls_query)
        
        # Временные ряды данных
        time_series = self._get_time_series_data(calls_query, period_days)
        
        # Распределение времени ожидания
        wait_time_distribution = self._get_wait_time_distribution(calls_query)
        
        return JsonResponse({
            **stats,
            'previous_total_calls': previous_stats.get('total_calls', 0),
            'previous_answered_calls': previous_stats.get('answered_calls', 0),
            'previous_answer_rate': previous_stats.get('answer_rate', 0),
            'time_labels': time_series['labels'],
            'calls_over_time': time_series['calls'],
            'wait_time_distribution': wait_time_distribution,
            'period_days': period_days,
            'timestamp': timezone.now().isoformat(),
        })
    
    def _calculate_call_stats(self, queryset):
        """Вычислить основную статистику звонков"""
        total_calls = queryset.count()
        answered_calls = queryset.filter(status='answered').count()
        missed_calls = queryset.filter(status='no_answer').count()
        busy_calls = queryset.filter(status='busy').count()
        failed_calls = queryset.filter(status='failed').count()
        
        # Средние показатели
        avg_duration = queryset.filter(
            status='answered',
            duration__isnull=False
        ).aggregate(avg=Avg('duration'))['avg'] or 0
        
        avg_wait_time = queryset.filter(
            queue_wait_time__isnull=False
        ).aggregate(avg=Avg('queue_wait_time'))['avg'] or 0
        
        # Процент ответов
        answer_rate = 0
        if total_calls > 0:
            answer_rate = round((answered_calls / total_calls) * 100, 1)
        
        return {
            'total_calls': total_calls,
            'answered_calls': answered_calls,
            'missed_calls': missed_calls,
            'busy_calls': busy_calls,
            'failed_calls': failed_calls,
            'avg_duration': round(avg_duration, 1),
            'avg_wait_time': round(avg_wait_time, 1),
            'answer_rate': answer_rate,
        }
    
    def _get_time_series_data(self, queryset, period_days):
        """Получить данные временных рядов"""
        if period_days <= 2:
            # Группировка по часам для коротких периодов
            time_data = queryset.extra({
                'hour': "strftime('%%Y-%%m-%%d %%H:00', start_time)"
            }).values('hour').annotate(
                call_count=Count('id')
            ).order_by('hour')
            
            labels = [item['hour'] for item in time_data]
            calls = [item['call_count'] for item in time_data]
            
        else:
            # Группировка по дням для длинных периодов
            time_data = queryset.extra({
                'day': "strftime('%%Y-%%m-%%d', start_time)"
            }).values('day').annotate(
                call_count=Count('id')
            ).order_by('day')
            
            labels = [item['day'] for item in time_data]
            calls = [item['call_count'] for item in time_data]
        
        return {
            'labels': labels,
            'calls': calls
        }
    
    def _get_wait_time_distribution(self, queryset):
        """Получить распределение времени ожидания"""
        # Категории времени ожидания в секундах
        categories = [
            (0, 30),      # 0-30 секунд
            (30, 60),     # 30-60 секунд  
            (60, 120),    # 1-2 минуты
            (120, 300),   # 2-5 минут
            (300, None)   # 5+ минут
        ]
        
        distribution = []
        
        for min_time, max_time in categories:
            query = queryset.filter(queue_wait_time__gte=min_time)
            if max_time:
                query = query.filter(queue_wait_time__lt=max_time)
            
            count = query.count()
            distribution.append(count)
        
        return distribution


class GroupPerformanceAPIView(View):
    """API для получения производительности групп"""
    
    def get(self, request):
        period_days = int(request.GET.get('period', 7))
        
        groups = NumberGroup.objects.filter(active=True)
        groups_data = []
        
        for group in groups:
            stats = call_statistics.get_group_statistics(group, period_days)
            
            # Текущая очередь
            current_queue = CallQueue.objects.filter(
                group=group,
                status='waiting'
            ).count()
            
            # Доступные агенты
            available_agents = group.get_available_members().count()
            total_agents = group.members.count()
            
            groups_data.append({
                'id': group.id,
                'name': group.name,
                'description': group.description,
                'current_queue': current_queue,
                'max_queue_size': group.max_queue_size,
                'available_agents': available_agents,
                'total_agents': total_agents,
                'distribution_strategy': group.get_distribution_strategy_display(),
                'stats': stats
            })
        
        return JsonResponse({
            'groups': groups_data,
            'timestamp': timezone.now().isoformat()
        })


class RecentCallsAPIView(View):
    """API для получения последних звонков"""
    
    def get(self, request):
        limit = int(request.GET.get('limit', 50))
        group_id = request.GET.get('group_id')
        
        calls_query = CallLog.objects.select_related(
            'routed_to_number__user',
            'routed_to_group',
            'routing_rule'
        ).order_by('-start_time')
        
        if group_id:
            try:
                group = NumberGroup.objects.get(id=group_id)
                calls_query = calls_query.filter(routed_to_group=group)
            except NumberGroup.DoesNotExist:
                pass
        
        calls = calls_query[:limit]
        
        calls_data = []
        for call in calls:
            # Форматируем данные звонка
            duration_str = '--'
            if call.duration:
                minutes, seconds = divmod(call.duration, 60)
                duration_str = f"{minutes}:{seconds:02d}"
            
            # Получаем информацию о группе
            group_name = call.routed_to_group.name if call.routed_to_group else '--'
            
            # Получаем информацию об агенте
            agent_name = '--'
            if call.routed_to_number and call.routed_to_number.user:
                agent_name = call.routed_to_number.user.get_full_name() or call.routed_to_number.user.username
            
            calls_data.append({
                'id': call.id,
                'session_id': call.session_id,
                'start_time': call.start_time.isoformat(),
                'caller_id': call.caller_id,
                'called_number': call.called_number,
                'direction': call.get_direction_display(),
                'status': call.status,
                'duration': call.duration,
                'duration_str': duration_str,
                'group_name': group_name,
                'agent_name': agent_name,
                'routing_rule': call.routing_rule.name if call.routing_rule else '--'
            })
        
        return JsonResponse({
            'calls': calls_data,
            'total_count': CallLog.objects.count(),
            'timestamp': timezone.now().isoformat()
        })


class LiveQueueAPIView(View):
    """API для получения данных очередей в реальном времени"""
    
    def get(self, request):
        """Получить текущее состояние всех очередей"""
        groups = NumberGroup.objects.filter(active=True)
        queues_data = []
        
        for group in groups:
            # Получаем текущую очередь
            queue_entries = CallQueue.objects.filter(
                group=group,
                status='waiting'
            ).order_by('queue_position')
            
            entries_data = []
            for entry in queue_entries:
                wait_time = entry.wait_time
                entries_data.append({
                    'id': entry.id,
                    'caller_id': entry.caller_id,
                    'position': entry.queue_position,
                    'wait_time': wait_time,
                    'estimated_wait': entry.estimated_wait_time,
                    'session_id': entry.session_id
                })
            
            # Статистика группы
            group_stats = call_statistics.get_group_statistics(group, days=1)
            
            queues_data.append({
                'group_id': group.id,
                'group_name': group.name,
                'current_size': len(entries_data),
                'max_queue_size': group.max_queue_size,
                'ring_timeout': group.ring_timeout,
                'queue_timeout': group.queue_timeout,
                'distribution_strategy': group.distribution_strategy,
                'entries': entries_data,
                'available_agents': group.get_available_members().count(),
                'total_agents': group.members.count(),
                'today_stats': group_stats
            })
        
        # Общая статистика
        total_waiting = CallQueue.objects.filter(status='waiting').count()
        total_capacity = NumberGroup.objects.filter(active=True).aggregate(
            total=Count('max_queue_size')
        )['total'] or 0
        
        return JsonResponse({
            'queues': queues_data,
            'summary': {
                'total_waiting': total_waiting,
                'total_capacity': total_capacity,
                'active_groups': len(queues_data)
            },
            'timestamp': timezone.now().isoformat()
        })


class SystemStatusAPIView(View):
    """API для получения статуса системы"""
    
    def get(self, request):
        """Получить общий статус системы VoIP"""
        
        # Статистика SIP аккаунтов
        total_accounts = SipAccount.objects.count()
        active_accounts = SipAccount.objects.filter(active=True).count()
        
        # Статистика номеров
        total_numbers = InternalNumber.objects.count()
        active_numbers = InternalNumber.objects.filter(active=True).count()
        available_numbers = InternalNumber.objects.filter(
            active=True,
            user__isnull=False,
            sip_account__active=True
        ).count()
        
        # Статистика групп
        total_groups = NumberGroup.objects.count()
        active_groups = NumberGroup.objects.filter(active=True).count()
        
        # Статистика правил
        total_rules = CallRoutingRule.objects.count()
        active_rules = CallRoutingRule.objects.filter(active=True).count()
        
        # Статистика звонков за сегодня
        today = timezone.now().date()
        today_calls = CallLog.objects.filter(start_time__date=today).count()
        today_answered = CallLog.objects.filter(
            start_time__date=today,
            status='answered'
        ).count()
        
        return JsonResponse({
            'accounts': {
                'total': total_accounts,
                'active': active_accounts,
                'utilization': round((active_accounts / total_accounts * 100), 1) if total_accounts > 0 else 0
            },
            'numbers': {
                'total': total_numbers,
                'active': active_numbers,
                'available': available_numbers
            },
            'groups': {
                'total': total_groups,
                'active': active_groups
            },
            'rules': {
                'total': total_rules,
                'active': active_rules
            },
            'today': {
                'calls': today_calls,
                'answered': today_answered,
                'answer_rate': round((today_answered / today_calls * 100), 1) if today_calls > 0 else 0
            },
            'timestamp': timezone.now().isoformat()
        })


# Декораторы для простого использования
@login_required
def dashboard_view(request):
    """Простая функция для дашборда"""
    view = CallDashboardView()
    return view.get(request)


@login_required  
def queue_monitor_view(request):
    """Простая функция для монитора очередей"""
    view = QueueMonitorView()
    return view.get(request)