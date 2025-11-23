"""
Утилиты для управления SIP аккаунтами пользователей
Аналогично системе телефонии Битрикс24
"""
import secrets
import string
from django.contrib.auth import get_user_model
from django.conf import settings
from voip.models import SipServer, InternalNumber, SipAccount


def generate_secure_password(length=12):
    """Генерирует безопасный пароль для SIP"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for i in range(length))


def get_default_sip_server():
    """Получить SIP сервер по умолчанию"""
    return SipServer.objects.filter(active=True).first()


def create_internal_number(user, server=None, number=None, password=None):
    """
    Создает внутренний номер для пользователя
    """
    if not server:
        server = get_default_sip_server()
        if not server:
            raise ValueError("No active SIP server found. Please create one first.")
    
    if not number:
        number = InternalNumber.generate_next_number(server)
    
    if not password:
        password = generate_secure_password()
    
    # Проверяем что номер не занят
    if InternalNumber.objects.filter(server=server, number=number).exists():
        raise ValueError(f"Internal number {number} already exists on server {server}")
    
    internal_number = InternalNumber.objects.create(
        server=server,
        number=number,
        user=user,
        password=password,
        display_name=user.get_full_name() or user.username,
        auto_generated=True,
        active=True
    )
    
    return internal_number


def create_sip_account_for_user(user, server=None, external_caller_id=None):
    """
    Создает полный SIP аккаунт для пользователя
    Включает создание внутреннего номера и SIP аккаунта
    """
    # Проверяем что у пользователя еще нет SIP аккаунта
    if hasattr(user, 'sip_account'):
        return user.sip_account
    
    # Создаем внутренний номер
    internal_number = create_internal_number(user, server)
    
    # Создаем SIP аккаунт
    sip_account = SipAccount.objects.create(
        user=user,
        internal_number=internal_number,
        external_caller_id=external_caller_id or '',
        can_make_external_calls=False,  # По умолчанию только внутренние звонки
        can_receive_external_calls=False,
        call_recording_enabled=True,
        voicemail_enabled=True,
        voicemail_email=user.email,
        max_concurrent_calls=2,
        active=True
    )
    
    return sip_account


def auto_create_sip_accounts_for_all_users():
    """
    Создает SIP аккаунты для всех пользователей у которых их нет
    Используется при инициализации системы
    """
    User = get_user_model()
    users_without_sip = User.objects.filter(sip_account__isnull=True)
    
    created_count = 0
    errors = []
    
    for user in users_without_sip:
        try:
            create_sip_account_for_user(user)
            created_count += 1
        except Exception as e:
            errors.append(f"Error creating SIP account for {user}: {e}")
    
    return {
        'created': created_count,
        'errors': errors
    }


def get_user_sip_config(user):
    """
    Получить SIP конфигурацию для пользователя в формате JsSIP
    """
    try:
        sip_account = user.sip_account
        if not sip_account.active:
            return None
        
        return sip_account.get_jssip_config()
    except SipAccount.DoesNotExist:
        return None


def bulk_update_sip_passwords(users=None, length=12):
    """
    Массовое обновление SIP паролей
    """
    if users is None:
        # Обновить для всех пользователей
        internal_numbers = InternalNumber.objects.filter(active=True)
    else:
        # Обновить для указанных пользователей
        internal_numbers = InternalNumber.objects.filter(
            user__in=users, 
            active=True
        )
    
    updated_count = 0
    for internal_number in internal_numbers:
        internal_number.password = generate_secure_password(length)
        internal_number.save()
        updated_count += 1
    
    return updated_count


def assign_external_permissions(user, can_make_external=True, can_receive_external=True, external_caller_id=None):
    """
    Назначить пользователю права на внешние звонки
    """
    try:
        sip_account = user.sip_account
        sip_account.can_make_external_calls = can_make_external
        sip_account.can_receive_external_calls = can_receive_external
        
        if external_caller_id:
            sip_account.external_caller_id = external_caller_id
            
        sip_account.save()
        return sip_account
    except SipAccount.DoesNotExist:
        raise ValueError(f"User {user} does not have a SIP account")


def get_available_internal_numbers(server=None, count=10):
    """
    Получить список доступных внутренних номеров
    """
    if not server:
        server = get_default_sip_server()
        if not server:
            return []
    
    available = []
    start_from = 1000
    
    for i in range(count):
        try:
            number = InternalNumber.generate_next_number(server, start_from + i)
            available.append(number)
        except Exception:
            continue
    
    return available


def setup_default_sip_server(name, host, websocket_uri, realm=None):
    """
    Настройка SIP сервера по умолчанию
    """
    server, created = SipServer.objects.get_or_create(
        host=host,
        defaults={
            'name': name,
            'websocket_uri': websocket_uri,
            'realm': realm or host,
            'active': True
        }
    )
    
    if not created:
        # Обновляем существующий
        server.name = name
        server.websocket_uri = websocket_uri
        server.realm = realm or host
        server.active = True
        server.save()
    
    return server


def migrate_user_to_new_server(user, new_server):
    """
    Перенос пользователя на новый SIP сервер
    """
    try:
        old_account = user.sip_account
        old_number = old_account.internal_number
        
        # Создаем новый внутренний номер на новом сервере
        new_internal_number = create_internal_number(
            user=user,
            server=new_server,
            number=old_number.number,  # Попробуем сохранить тот же номер
            password=old_number.password
        )
        
        # Обновляем SIP аккаунт
        old_account.internal_number = new_internal_number
        old_account.save()
        
        # Удаляем старый внутренний номер
        old_number.delete()
        
        return old_account
    except Exception as e:
        raise ValueError(f"Failed to migrate user {user} to new server: {e}")