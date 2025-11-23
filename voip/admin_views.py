"""
Веб-интерфейс для команд управления VoIP системой
Интеграция команд в Django админку
"""
import logging
from django import forms
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views import View
from django.http import JsonResponse
from voip.models import (
    SipServer, NumberGroup, CallRoutingRule, InternalNumber, 
    SipAccount, CallLog
)
from voip.utils.sip_helpers import (
    setup_default_sip_server, auto_create_sip_accounts_for_all_users,
    get_available_internal_numbers
)
from voip.utils.routing import call_statistics

logger = logging.getLogger(__name__)


class SipServerSetupForm(forms.Form):
    """Форма для настройки SIP сервера"""
    name = forms.CharField(
        label='Название сервера',
        max_length=100,
        initial='Default SIP Server',
        widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 300px;'})
    )
    host = forms.CharField(
        label='Хост сервера',
        max_length=255,
        help_text='Домен или IP адрес SIP сервера (например, sip.example.com)',
        widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 300px;'})
    )
    websocket_uri = forms.CharField(
        label='WebSocket URI',
        max_length=255,
        help_text='WSS URI для WebRTC (например, wss://sip.example.com:7443)',
        widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 400px;'})
    )
    realm = forms.CharField(
        label='Realm (опционально)',
        max_length=255,
        required=False,
        help_text='SIP realm, обычно такой же как хост',
        widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 300px;'})
    )
    create_accounts = forms.BooleanField(
        label='Создать SIP аккаунты для всех пользователей',
        required=False,
        initial=True,
        help_text='Автоматически создать внутренние номера и SIP аккаунты'
    )


class NumberGroupCreateForm(forms.Form):
    """Форма для создания группы номеров"""
    name = forms.CharField(
        label='Название группы',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 300px;'})
    )
    description = forms.CharField(
        label='Описание',
        required=False,
        widget=forms.Textarea(attrs={'class': 'vLargeTextField', 'rows': 3, 'style': 'width: 400px;'})
    )
    server = forms.ModelChoiceField(
        label='SIP сервер',
        queryset=SipServer.objects.filter(active=True),
        widget=forms.Select(attrs={'class': 'vForeignKeyRawIdAdminField'})
    )
    distribution_strategy = forms.ChoiceField(
        label='Стратегия распределения',
        choices=[
            ('round_robin', 'Round Robin (по очереди)'),
            ('random', 'Random (случайно)'),
            ('priority', 'Priority (по приоритету)'),
            ('all_ring', 'Ring All (звонить всем)'),
            ('least_recent', 'Least Recent (кому давно не звонили)'),
        ],
        initial='round_robin',
        widget=forms.Select(attrs={'class': 'vForeignKeyRawIdAdminField'})
    )
    members = forms.ModelMultipleChoiceField(
        label='Участники группы',
        queryset=InternalNumber.objects.filter(active=True),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'vCheckboxSelectMultiple'})
    )
    ring_timeout = forms.IntegerField(
        label='Время звонка (секунды)',
        initial=30,
        min_value=5,
        max_value=300,
        widget=forms.NumberInput(attrs={'class': 'vIntegerField'})
    )
    max_queue_size = forms.IntegerField(
        label='Максимальный размер очереди',
        initial=10,
        min_value=1,
        max_value=100,
        widget=forms.NumberInput(attrs={'class': 'vIntegerField'})
    )


class CallRoutingRuleCreateForm(forms.Form):
    """Форма для создания правила маршрутизации"""
    name = forms.CharField(
        label='Название правила',
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 300px;'})
    )
    description = forms.CharField(
        label='Описание',
        required=False,
        widget=forms.Textarea(attrs={'class': 'vLargeTextField', 'rows': 3, 'style': 'width: 400px;'})
    )
    priority = forms.IntegerField(
        label='Приоритет',
        initial=100,
        help_text='Меньшее число = выше приоритет',
        widget=forms.NumberInput(attrs={'class': 'vIntegerField'})
    )
    caller_id_pattern = forms.CharField(
        label='Паттерн номера звонящего (regex)',
        required=False,
        help_text='Например: ^\\+7 для российских номеров, ^8800 для бесплатных',
        widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 300px;'})
    )
    called_number_pattern = forms.CharField(
        label='Паттерн вызываемого номера (regex)',
        required=False,
        help_text='Например: ^100 для номеров начинающихся с 100',
        widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 300px;'})
    )
    action = forms.ChoiceField(
        label='Действие',
        choices=[
            ('route_to_number', 'Маршрутизация на номер'),
            ('route_to_group', 'Маршрутизация в группу'),
            ('forward_external', 'Переадресация на внешний номер'),
            ('play_announcement', 'Воспроизвести объявление'),
            ('hangup', 'Сбросить звонок'),
        ],
        widget=forms.Select(attrs={'class': 'vForeignKeyRawIdAdminField'})
    )
    target_number = forms.ModelChoiceField(
        label='Целевой номер',
        queryset=InternalNumber.objects.filter(active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'vForeignKeyRawIdAdminField'})
    )
    target_group = forms.ModelChoiceField(
        label='Целевая группа',
        queryset=NumberGroup.objects.filter(active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'vForeignKeyRawIdAdminField'})
    )
    target_external = forms.CharField(
        label='Внешний номер',
        required=False,
        help_text='Номер для переадресации (например, +79001234567)',
        widget=forms.TextInput(attrs={'class': 'vTextField', 'style': 'width: 200px;'})
    )
    announcement_text = forms.CharField(
        label='Текст объявления',
        required=False,
        widget=forms.Textarea(attrs={'class': 'vLargeTextField', 'rows': 3, 'style': 'width: 400px;'})
    )


class StatisticsFilterForm(forms.Form):
    """Форма для фильтров статистики"""
    period_days = forms.IntegerField(
        label='Период (дни)',
        initial=7,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={'class': 'vIntegerField'})
    )
    group = forms.ModelChoiceField(
        label='Группа (опционально)',
        queryset=NumberGroup.objects.filter(active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'vForeignKeyRawIdAdminField'})
    )


@method_decorator(staff_member_required, name='dispatch')
class VoipManagementView(View):
    """Главный вид управления VoIP системой"""
    
    def get(self, request):
        # Собираем статистику для дашборда
        context = {
            'title': 'Управление VoIP системой',
            'has_permission': True,
            'site_header': admin.site.site_header,
            'site_title': admin.site.site_title,
            'statistics': self._get_system_statistics(),
        }
        
        return render(request, 'admin/voip/management_dashboard.html', context)
    
    def _get_system_statistics(self):
        """Получить статистику системы"""
        try:
            return {
                'total_servers': SipServer.objects.count(),
                'active_servers': SipServer.objects.filter(active=True).count(),
                'total_numbers': InternalNumber.objects.count(),
                'active_numbers': InternalNumber.objects.filter(active=True).count(),
                'total_accounts': SipAccount.objects.count(),
                'active_accounts': SipAccount.objects.filter(active=True).count(),
                'total_groups': NumberGroup.objects.count(),
                'active_groups': NumberGroup.objects.filter(active=True).count(),
                'total_rules': CallRoutingRule.objects.count(),
                'active_rules': CallRoutingRule.objects.filter(active=True).count(),
                'today_calls': CallLog.objects.filter(
                    start_time__date=timezone.now().date()
                ).count() if 'timezone' in globals() else 0,
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}


@method_decorator(staff_member_required, name='dispatch')
class SipServerSetupView(View):
    """Настройка SIP сервера"""
    
    def get(self, request):
        form = SipServerSetupForm()
        
        context = {
            'title': 'Настройка SIP сервера',
            'has_permission': True,
            'form': form,
            'existing_servers': SipServer.objects.all(),
        }
        
        return render(request, 'admin/voip/sip_server_setup.html', context)
    
    def post(self, request):
        form = SipServerSetupForm(request.POST)
        
        if form.is_valid():
            try:
                # Создаем или обновляем сервер
                server = setup_default_sip_server(
                    name=form.cleaned_data['name'],
                    host=form.cleaned_data['host'],
                    websocket_uri=form.cleaned_data['websocket_uri'],
                    realm=form.cleaned_data.get('realm')
                )
                
                messages.success(
                    request,
                    f'SIP сервер "{server.name}" успешно настроен!'
                )
                
                # Создаем аккаунты если нужно
                if form.cleaned_data['create_accounts']:
                    result = auto_create_sip_accounts_for_all_users()
                    
                    if result['created'] > 0:
                        messages.success(
                            request,
                            f'Создано {result["created"]} SIP аккаунтов для пользователей'
                        )
                    
                    if result['errors']:
                        for error in result['errors'][:3]:  # Показываем только первые 3 ошибки
                            messages.warning(request, error)
                
                return redirect('admin:voip-management')
                
            except Exception as e:
                logger.error(f"Ошибка настройки SIP сервера: {e}")
                messages.error(
                    request,
                    f'Ошибка настройки сервера: {str(e)}'
                )
        
        context = {
            'title': 'Настройка SIP сервера',
            'has_permission': True,
            'form': form,
            'existing_servers': SipServer.objects.all(),
        }
        
        return render(request, 'admin/voip/sip_server_setup.html', context)


@method_decorator(staff_member_required, name='dispatch')
class NumberGroupCreateView(View):
    """Создание группы номеров"""
    
    def get(self, request):
        form = NumberGroupCreateForm()
        
        context = {
            'title': 'Создание группы номеров',
            'has_permission': True,
            'form': form,
            'existing_groups': NumberGroup.objects.all(),
        }
        
        return render(request, 'admin/voip/number_group_create.html', context)
    
    def post(self, request):
        form = NumberGroupCreateForm(request.POST)
        
        if form.is_valid():
            try:
                # Создаем группу
                group = NumberGroup.objects.create(
                    name=form.cleaned_data['name'],
                    description=form.cleaned_data['description'],
                    server=form.cleaned_data['server'],
                    distribution_strategy=form.cleaned_data['distribution_strategy'],
                    ring_timeout=form.cleaned_data['ring_timeout'],
                    max_queue_size=form.cleaned_data['max_queue_size'],
                )
                
                # Добавляем участников
                if form.cleaned_data['members']:
                    group.members.set(form.cleaned_data['members'])
                
                messages.success(
                    request,
                    f'Группа номеров "{group.name}" успешно создана! '
                    f'Участников: {group.members.count()}'
                )
                
                return redirect('admin:voip-management')
                
            except Exception as e:
                logger.error(f"Ошибка создания группы номеров: {e}")
                messages.error(
                    request,
                    f'Ошибка создания группы: {str(e)}'
                )
        
        context = {
            'title': 'Создание группы номеров',
            'has_permission': True,
            'form': form,
            'existing_groups': NumberGroup.objects.all(),
        }
        
        return render(request, 'admin/voip/number_group_create.html', context)


@method_decorator(staff_member_required, name='dispatch')
class CallRoutingRuleCreateView(View):
    """Создание правила маршрутизации"""
    
    def get(self, request):
        form = CallRoutingRuleCreateForm()
        
        context = {
            'title': 'Создание правила маршрутизации',
            'has_permission': True,
            'form': form,
            'existing_rules': CallRoutingRule.objects.all().order_by('priority'),
        }
        
        return render(request, 'admin/voip/routing_rule_create.html', context)
    
    def post(self, request):
        form = CallRoutingRuleCreateForm(request.POST)
        
        if form.is_valid():
            try:
                # Создаем правило
                rule = CallRoutingRule.objects.create(
                    name=form.cleaned_data['name'],
                    description=form.cleaned_data['description'],
                    priority=form.cleaned_data['priority'],
                    caller_id_pattern=form.cleaned_data['caller_id_pattern'],
                    called_number_pattern=form.cleaned_data['called_number_pattern'],
                    action=form.cleaned_data['action'],
                    target_number=form.cleaned_data.get('target_number'),
                    target_group=form.cleaned_data.get('target_group'),
                    target_external=form.cleaned_data.get('target_external'),
                    announcement_text=form.cleaned_data.get('announcement_text'),
                )
                
                messages.success(
                    request,
                    f'Правило маршрутизации "{rule.name}" успешно создано! '
                    f'Приоритет: {rule.priority}'
                )
                
                return redirect('admin:voip-management')
                
            except Exception as e:
                logger.error(f"Ошибка создания правила маршрутизации: {e}")
                messages.error(
                    request,
                    f'Ошибка создания правила: {str(e)}'
                )
        
        context = {
            'title': 'Создание правила маршрутизации',
            'has_permission': True,
            'form': form,
            'existing_rules': CallRoutingRule.objects.all().order_by('priority'),
        }
        
        return render(request, 'admin/voip/routing_rule_create.html', context)


@method_decorator(staff_member_required, name='dispatch')
class StatisticsView(View):
    """Просмотр статистики"""
    
    def get(self, request):
        form = StatisticsFilterForm()
        stats_data = None
        
        # Если есть параметры, получаем статистику
        if request.GET:
            form = StatisticsFilterForm(request.GET)
            if form.is_valid():
                period_days = form.cleaned_data['period_days']
                group = form.cleaned_data.get('group')
                
                if group:
                    stats_data = call_statistics.get_group_statistics(group, period_days)
                    stats_data['group_name'] = group.name
                else:
                    stats_data = self._get_general_statistics(period_days)
                
                stats_data['period_days'] = period_days
        
        context = {
            'title': 'Статистика звонков',
            'has_permission': True,
            'form': form,
            'stats_data': stats_data,
            'groups': NumberGroup.objects.filter(active=True),
        }
        
        return render(request, 'admin/voip/statistics.html', context)
    
    def _get_general_statistics(self, period_days):
        """Получить общую статистику"""
        try:
            from datetime import timedelta
            from django.utils import timezone
            from django.db.models import Count
            
            start_date = timezone.now() - timedelta(days=period_days)
            
            calls = CallLog.objects.filter(start_time__gte=start_date)
            
            return {
                'total_calls': calls.count(),
                'answered_calls': calls.filter(status='answered').count(),
                'missed_calls': calls.filter(status='no_answer').count(),
                'busy_calls': calls.filter(status='busy').count(),
                'failed_calls': calls.filter(status='failed').count(),
                'answer_rate': 0,  # Будет вычислено в шаблоне
            }
        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}


@staff_member_required
def quick_actions_api(request):
    """API для быстрых действий"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    action = request.POST.get('action')
    
    try:
        if action == 'sync_accounts':
            result = auto_create_sip_accounts_for_all_users()
            return JsonResponse({
                'success': True,
                'message': f'Создано {result["created"]} аккаунтов',
                'errors': result['errors'][:5]  # Показываем только первые 5 ошибок
            })
        
        elif action == 'test_routing':
            caller_id = request.POST.get('caller_id', '+79001234567')
            called_number = request.POST.get('called_number', '100')
            
            from voip.utils.routing import route_call
            result = route_call(caller_id, called_number, f'test_{timezone.now().timestamp()}')
            
            return JsonResponse({
                'success': True,
                'routing_result': result
            })
        
        elif action == 'check_health':
            from voip.utils.notifications import check_system_health
            check_system_health()
            
            return JsonResponse({
                'success': True,
                'message': 'Проверка здоровья системы выполнена'
            })
        
        else:
            return JsonResponse({'error': 'Unknown action'}, status=400)
    
    except Exception as e:
        logger.error(f"Ошибка выполнения действия {action}: {e}")
        return JsonResponse({'error': str(e)}, status=500)


# Регистрируем URL'ы в AdminSite
def get_voip_admin_urls():
    """Получить URL'ы для админки VoIP"""
    return [
        path('voip-management/', VoipManagementView.as_view(), name='voip-management'),
        path('voip-management/setup-server/', SipServerSetupView.as_view(), name='voip-setup-server'),
        path('voip-management/create-group/', NumberGroupCreateView.as_view(), name='voip-create-group'),
        path('voip-management/create-rule/', CallRoutingRuleCreateView.as_view(), name='voip-create-rule'),
        path('voip-management/statistics/', StatisticsView.as_view(), name='voip-statistics'),
        path('voip-management/api/quick-actions/', quick_actions_api, name='voip-quick-actions'),
    ]