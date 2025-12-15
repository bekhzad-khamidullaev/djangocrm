# Asterisk Integration Examples

## Быстрые примеры использования

### 1. Базовое подключение и тест

```python
from voip.ami import AmiClient
from voip.utils import load_asterisk_config

# Загрузка конфигурации
config = load_asterisk_config()

# Создание клиента
client = AmiClient(config)

# Подключение
client.connect()

# Проверка ping
response = client.send_action_sync('Ping')
print(f"Ping response: {response}")

# Закрытие соединения
client.close()
```

### 2. Инициация исходящего звонка

```python
from voip.ami import AmiClient
from voip.integrations.asterisk_control import AsteriskCallControl
from voip.utils import load_asterisk_config

config = load_asterisk_config()
client = AmiClient(config)
client.connect()

control = AsteriskCallControl(client)

# Простой звонок
result = control.originate(
    channel='SIP/101',
    extension='1234567890',
    context='outbound'
)

if result.get('Response') == 'Success':
    print("Call initiated successfully")
else:
    print(f"Error: {result.get('Message')}")

client.close()
```

### 3. Мониторинг очередей в реальном времени

```python
import time
from voip.ami import AmiClient
from voip.integrations.asterisk_queue import AsteriskQueueMonitor
from voip.utils import load_asterisk_config

config = load_asterisk_config()
client = AmiClient(config)
client.connect()

monitor = AsteriskQueueMonitor(client)

while True:
    summary = monitor.get_queue_summary('support')
    
    print(f"\n{'='*50}")
    print(f"Queue: {summary['queue']}")
    print(f"Calls waiting: {summary['calls_waiting']}")
    print(f"Available agents: {summary['available_agents']}")
    print(f"Busy agents: {summary['busy_agents']}")
    print(f"Longest wait: {summary['longest_wait']}s")
    
    if summary['calls_waiting'] > 5:
        print("⚠️  WARNING: High call volume!")
    
    time.sleep(5)
```

### 4. Управление агентами очереди

```python
from voip.ami import AmiClient
from voip.integrations.asterisk_queue import AsteriskQueueMonitor
from voip.utils import load_asterisk_config

config = load_asterisk_config()
client = AmiClient(config)
client.connect()

monitor = AsteriskQueueMonitor(client)

# Добавить агента
monitor.add_queue_member(
    queue='support',
    interface='SIP/101',
    member_name='John Doe',
    penalty=0
)

# Поставить на паузу (обед)
monitor.pause_queue_member(
    queue='support',
    interface='SIP/101',
    paused=True,
    reason='Lunch break'
)

# Возобновить работу
time.sleep(3600)  # Через час
monitor.pause_queue_member(
    queue='support',
    interface='SIP/101',
    paused=False
)

# Удалить из очереди (конец смены)
monitor.remove_queue_member(
    queue='support',
    interface='SIP/101'
)

client.close()
```

### 5. Health check и алерты

```python
from voip.ami import AmiClient
from voip.utils.asterisk_health import AsteriskHealthCheck
from voip.utils import load_asterisk_config

config = load_asterisk_config()
client = AmiClient(config)
client.connect()

health = AsteriskHealthCheck(client)

# Полная проверка системы
report = health.get_full_health_report()

if report['overall_status'] != 'healthy':
    print(f"⚠️  ALERT: System status is {report['overall_status']}")
    
    # Проверяем детали
    if report['checks']['connection']['status'] != 'healthy':
        print("❌ Connection issues detected")
    
    if report['checks']['channels']['status'] != 'healthy':
        print("❌ Channel availability issues")
        sip = report['checks']['channels']['sip_peers']
        print(f"   Online: {sip['online']}/{sip['total']}")
    
    if report['checks']['queues']['status'] != 'healthy':
        print("❌ Queue issues detected")
        alerts = report['checks']['queues'].get('alerts', [])
        for alert in alerts:
            if alert['type'] == 'no_agents':
                print(f"   No agents in queue {alert['queue']}")
            elif alert['type'] == 'long_wait':
                print(f"   Long wait in queue {alert['queue']}: {alert['wait_time']}s")

client.close()
```

### 6. Импорт CDR и анализ

```python
from datetime import datetime, timedelta
from voip.utils.cdr_import import AsteriskCDRImporter

importer = AsteriskCDRImporter()

# Импорт за последнюю неделю
db_config = {
    'host': 'asterisk.example.com',
    'user': 'asteriskcdr',
    'password': 'secure_password',
    'database': 'asteriskcdrdb',
}

end_date = datetime.now()
start_date = end_date - timedelta(days=7)

result = importer.import_from_database(db_config, start_date, end_date)

print(f"Import Summary:")
print(f"  Imported: {result['imported']}")
print(f"  Skipped: {result['skipped']}")
print(f"  Errors: {result['errors']}")

if result['error_details']:
    print("\nErrors:")
    for error in result['error_details']:
        print(f"  - {error}")

# Анализ импортированных звонков
from crm.models.others import CallLog

recent_calls = CallLog.objects.filter(
    created_date__gte=start_date
).order_by('-created_date')

total = recent_calls.count()
completed = recent_calls.filter(duration__gt=0).count()
missed = total - completed

print(f"\nCall Statistics:")
print(f"  Total calls: {total}")
print(f"  Completed: {completed} ({completed/total*100:.1f}%)")
print(f"  Missed: {missed} ({missed/total*100:.1f}%)")
```

### 7. Переадресация звонка

```python
from voip.ami import AmiClient
from voip.integrations.asterisk_control import AsteriskCallControl
from voip.utils import load_asterisk_config

config = load_asterisk_config()
client = AmiClient(config)
client.connect()

control = AsteriskCallControl(client)

# Найти активный канал
channels = control.get_active_channels()

if channels:
    active_channel = channels[0]['Channel']
    
    # Перевести на другого агента
    result = control.transfer(
        channel=active_channel,
        extension='102',
        context='internal'
    )
    
    if result.get('Response') == 'Success':
        print("Call transferred successfully")

client.close()
```

### 8. Парковка и возврат звонка

```python
from voip.ami import AmiClient
from voip.integrations.asterisk_control import AsteriskCallControl
from voip.utils import load_asterisk_config
import time

config = load_asterisk_config()
client = AmiClient(config)
client.connect()

control = AsteriskCallControl(client)

# Припарковать звонок
result = control.park(
    channel='SIP/101-00000001',
    parking_lot='default',
    timeout=60
)

if result.get('Response') == 'Success':
    parking_space = result.get('ParkingSpace', '700')
    print(f"Call parked at extension: {parking_space}")
    
    # Вернуть звонок через 30 секунд
    time.sleep(30)
    
    # Набрать номер парковки для возврата
    control.originate(
        channel='SIP/102',
        extension=parking_space,
        context='parkedcalls'
    )

client.close()
```

### 9. Прослушивание звонка (Spy/Whisper)

```python
from voip.ami import AmiClient
from voip.integrations.asterisk_control import AsteriskCallControl
from voip.utils import load_asterisk_config

config = load_asterisk_config()
client = AmiClient(config)
client.connect()

control = AsteriskCallControl(client)

# Прослушивание (только слушать)
control.spy(
    spy_channel='SIP/supervisor',
    target_channel='SIP/agent-00000001',
    mode='listen'
)

# Шептание (говорить только агенту)
control.spy(
    spy_channel='SIP/supervisor',
    target_channel='SIP/agent-00000001',
    mode='whisper'
)

# Вмешательство (говорить всем)
control.spy(
    spy_channel='SIP/supervisor',
    target_channel='SIP/agent-00000001',
    mode='barge'
)

client.close()
```

### 10. Автоматическое управление очередями на основе нагрузки

```python
from voip.ami import AmiClient
from voip.integrations.asterisk_queue import AsteriskQueueMonitor
from voip.utils import load_asterisk_config
import time

config = load_asterisk_config()
client = AmiClient(config)
client.connect()

monitor = AsteriskQueueMonitor(client)

# Пул агентов по уровням
tier1_agents = ['SIP/101', 'SIP/102', 'SIP/103']
tier2_agents = ['SIP/201', 'SIP/202']
tier3_agents = ['SIP/301', 'SIP/302', 'SIP/303', 'SIP/304']

while True:
    summary = monitor.get_queue_summary('support')
    calls_waiting = summary['calls_waiting']
    available_agents = summary['available_agents']
    
    # Базовые агенты всегда активны (penalty=0)
    for agent in tier1_agents:
        if agent not in [m['location'] for m in summary['members']]:
            monitor.add_queue_member('support', agent, penalty=0)
    
    # Если более 5 звонков в очереди - добавить tier2
    if calls_waiting > 5:
        for agent in tier2_agents:
            if agent not in [m['location'] for m in summary['members']]:
                monitor.add_queue_member('support', agent, penalty=1)
    
    # Если более 10 звонков - добавить tier3
    if calls_waiting > 10:
        for agent in tier3_agents:
            if agent not in [m['location'] for m in summary['members']]:
                monitor.add_queue_member('support', agent, penalty=2)
    
    # Если очередь пустая - убрать tier3
    if calls_waiting == 0:
        for agent in tier3_agents:
            try:
                monitor.remove_queue_member('support', agent)
            except:
                pass
    
    time.sleep(30)
```

## Django Views примеры

### REST API endpoint для статуса очереди

```python
# views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response
from voip.ami import AmiClient
from voip.integrations.asterisk_queue import AsteriskQueueMonitor
from voip.utils import load_asterisk_config

@api_view(['GET'])
def queue_status(request, queue_name):
    """Get real-time queue status"""
    try:
        config = load_asterisk_config()
        client = AmiClient(config)
        client.connect()
        
        monitor = AsteriskQueueMonitor(client)
        summary = monitor.get_queue_summary(queue_name)
        
        client.close()
        
        return Response({
            'success': True,
            'queue': summary
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)

@api_view(['POST'])
def pause_agent(request):
    """Pause/unpause agent in queue"""
    queue = request.data.get('queue')
    interface = request.data.get('interface')
    paused = request.data.get('paused', True)
    reason = request.data.get('reason', '')
    
    try:
        config = load_asterisk_config()
        client = AmiClient(config)
        client.connect()
        
        monitor = AsteriskQueueMonitor(client)
        result = monitor.pause_queue_member(queue, interface, paused, reason)
        
        client.close()
        
        return Response({
            'success': result.get('Response') == 'Success',
            'message': result.get('Message', '')
        })
    except Exception as e:
        return Response({
            'success': False,
            'error': str(e)
        }, status=500)
```

## Celery Tasks примеры

### Периодические задачи для мониторинга

```python
# tasks.py
from celery import shared_task
from voip.ami import AmiClient
from voip.utils.asterisk_health import AsteriskHealthCheck
from voip.utils import load_asterisk_config
from django.core.mail import send_mail

@shared_task
def check_asterisk_health():
    """Periodic health check"""
    try:
        config = load_asterisk_config()
        client = AmiClient(config)
        client.connect()
        
        health = AsteriskHealthCheck(client)
        report = health.get_full_health_report()
        
        if report['overall_status'] != 'healthy':
            # Отправить алерт администраторам
            send_mail(
                subject=f"Asterisk Alert: {report['overall_status']}",
                message=f"Asterisk system status: {report['overall_status']}\n\n"
                        f"Details: {report}",
                from_email='alerts@example.com',
                recipient_list=['admin@example.com'],
            )
        
        client.close()
        
    except Exception as e:
        # Критическая ошибка - Asterisk недоступен
        send_mail(
            subject="CRITICAL: Asterisk Unavailable",
            message=f"Cannot connect to Asterisk: {str(e)}",
            from_email='alerts@example.com',
            recipient_list=['admin@example.com'],
        )

@shared_task
def import_daily_cdr():
    """Import yesterday's CDR"""
    from datetime import datetime, timedelta
    from voip.utils.cdr_import import AsteriskCDRImporter
    
    importer = AsteriskCDRImporter()
    
    db_config = {
        'host': 'asterisk.example.com',
        'user': 'asteriskcdr',
        'password': 'password',
        'database': 'asteriskcdrdb',
    }
    
    yesterday = datetime.now() - timedelta(days=1)
    start = yesterday.replace(hour=0, minute=0, second=0)
    end = yesterday.replace(hour=23, minute=59, second=59)
    
    result = importer.import_from_database(db_config, start, end)
    
    return result

# В settings.py добавить расписание:
# CELERY_BEAT_SCHEDULE = {
#     'check-asterisk-health': {
#         'task': 'voip.tasks.check_asterisk_health',
#         'schedule': 300.0,  # Каждые 5 минут
#     },
#     'import-daily-cdr': {
#         'task': 'voip.tasks.import_daily_cdr',
#         'schedule': crontab(hour=1, minute=0),  # Каждый день в 01:00
#     },
# }
```

## Полезные советы

### 1. Обработка ошибок

```python
from voip.ami import AmiClient

try:
    client = AmiClient(config)
    client.connect()
    # ... операции
except ConnectionError as e:
    print(f"Connection failed: {e}")
except TimeoutError as e:
    print(f"Operation timed out: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    if client:
        client.close()
```

### 2. Context manager

```python
from contextlib import contextmanager

@contextmanager
def asterisk_client():
    config = load_asterisk_config()
    client = AmiClient(config)
    client.connect()
    try:
        yield client
    finally:
        client.close()

# Использование
with asterisk_client() as client:
    control = AsteriskCallControl(client)
    control.originate('SIP/101', '1234567890')
```

### 3. Логирование

```python
import logging

logger = logging.getLogger(__name__)

def make_call_with_logging(channel, extension):
    logger.info(f"Initiating call from {channel} to {extension}")
    
    try:
        with asterisk_client() as client:
            control = AsteriskCallControl(client)
            result = control.originate(channel, extension)
            
            if result.get('Response') == 'Success':
                logger.info(f"Call initiated successfully")
            else:
                logger.error(f"Call failed: {result.get('Message')}")
            
            return result
    except Exception as e:
        logger.exception(f"Error initiating call: {e}")
        raise
```

---

Больше примеров и документации: [docs/site/asterisk_integration_guide.md](../../docs/site/asterisk_integration_guide.md)
