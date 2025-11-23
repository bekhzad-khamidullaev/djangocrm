"""
Команда для настройки системы SIP телефонии
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from voip.models import SipServer, InternalNumber, SipAccount
from voip.utils.sip_helpers import (
    setup_default_sip_server, 
    auto_create_sip_accounts_for_all_users,
    get_available_internal_numbers
)


class Command(BaseCommand):
    help = 'Настройка системы SIP телефонии'

    def add_arguments(self, parser):
        parser.add_argument(
            '--server-name',
            type=str,
            default='Default SIP Server',
            help='Название SIP сервера'
        )
        parser.add_argument(
            '--server-host',
            type=str,
            required=True,
            help='Хост SIP сервера (например, sip.example.com)'
        )
        parser.add_argument(
            '--websocket-uri',
            type=str,
            required=True,
            help='WebSocket URI (например, wss://sip.example.com:7443)'
        )
        parser.add_argument(
            '--realm',
            type=str,
            help='SIP realm (по умолчанию как server-host)'
        )
        parser.add_argument(
            '--create-accounts',
            action='store_true',
            help='Создать SIP аккаунты для всех существующих пользователей'
        )
        parser.add_argument(
            '--list-available-numbers',
            action='store_true',
            help='Показать доступные внутренние номера'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно обновить существующий сервер'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🎯 Настройка системы SIP телефонии')
        )
        
        # Создание/настройка SIP сервера
        if options['server_host'] and options['websocket_uri']:
            self._setup_server(options)
        
        # Создание SIP аккаунтов
        if options['create_accounts']:
            self._create_accounts()
        
        # Показать доступные номера
        if options['list_available_numbers']:
            self._list_available_numbers()
    
    def _setup_server(self, options):
        """Настройка SIP сервера"""
        self.stdout.write('📡 Настройка SIP сервера...')
        
        try:
            server = setup_default_sip_server(
                name=options['server_name'],
                host=options['server_host'],
                websocket_uri=options['websocket_uri'],
                realm=options.get('realm')
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ SIP сервер настроен: {server.name} ({server.host})'
                )
            )
            self.stdout.write(f'   WebSocket URI: {server.websocket_uri}')
            self.stdout.write(f'   Realm: {server.sip_domain}')
            
        except Exception as e:
            raise CommandError(f'Ошибка настройки SIP сервера: {e}')
    
    def _create_accounts(self):
        """Создание SIP аккаунтов для пользователей"""
        self.stdout.write('👥 Создание SIP аккаунтов для пользователей...')
        
        User = get_user_model()
        total_users = User.objects.count()
        
        if total_users == 0:
            self.stdout.write(
                self.style.WARNING('⚠️  Нет пользователей в системе')
            )
            return
        
        result = auto_create_sip_accounts_for_all_users()
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Создано SIP аккаунтов: {result["created"]} из {total_users}'
            )
        )
        
        if result['errors']:
            self.stdout.write(
                self.style.ERROR('❌ Ошибки при создании аккаунтов:')
            )
            for error in result['errors']:
                self.stdout.write(f'   - {error}')
    
    def _list_available_numbers(self):
        """Показать доступные внутренние номера"""
        self.stdout.write('📞 Доступные внутренние номера:')
        
        try:
            server = SipServer.objects.filter(active=True).first()
            if not server:
                self.stdout.write(
                    self.style.ERROR('❌ Нет активных SIP серверов')
                )
                return
            
            available_numbers = get_available_internal_numbers(server, count=20)
            
            if available_numbers:
                for number in available_numbers:
                    self.stdout.write(f'   📱 {number}')
            else:
                self.stdout.write(
                    self.style.WARNING('⚠️  Нет доступных номеров')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка получения номеров: {e}')
            )
    
    def _show_statistics(self):
        """Показать статистику системы"""
        self.stdout.write('\n📊 Статистика системы:')
        
        servers_count = SipServer.objects.filter(active=True).count()
        numbers_count = InternalNumber.objects.filter(active=True).count()
        accounts_count = SipAccount.objects.filter(active=True).count()
        
        self.stdout.write(f'   🏢 Активных SIP серверов: {servers_count}')
        self.stdout.write(f'   📱 Внутренних номеров: {numbers_count}')
        self.stdout.write(f'   👤 SIP аккаунтов: {accounts_count}')
        
        User = get_user_model()
        users_without_sip = User.objects.filter(sip_account__isnull=True).count()
        
        if users_without_sip > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'   ⚠️  Пользователей без SIP: {users_without_sip}'
                )
            )
            self.stdout.write(
                '   💡 Запустите с --create-accounts для создания аккаунтов'
            )