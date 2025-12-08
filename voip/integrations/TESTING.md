# Testing Asterisk Integration

## Руководство по тестированию интеграции с Asterisk

### Предварительные требования

1. Asterisk должен быть установлен и запущен
2. AMI должен быть настроен и доступен
3. Django CRM должен быть настроен с корректными credentials

### Быстрая проверка

```bash
# Базовый тест подключения
python manage.py test_asterisk_connection

# Ожидаемый результат:
# Testing Asterisk AMI Connection
# ================================
# Host: 192.168.1.100
# Port: 5038
# Username: django_crm
# SSL: False
#
# Connecting to Asterisk AMI... OK
#
# Connection Test
# ===============
# ✓ Connected (response time: 15.3ms)
```

### Unit Tests

Создайте файл `tests/voip/test_asterisk_integration.py`:

```python
from django.test import TestCase
from unittest.mock import Mock, patch
from voip.ami import AmiClient
from voip.integrations.asterisk_control import AsteriskCallControl
from voip.integrations.asterisk_queue import AsteriskQueueMonitor
from voip.utils.asterisk_health import AsteriskHealthCheck


class AsteriskConnectionTest(TestCase):
    """Тесты подключения к Asterisk"""
    
    def setUp(self):
        self.config = {
            'HOST': 'localhost',
            'PORT': 5038,
            'USERNAME': 'test',
            'SECRET': 'test',
            'USE_SSL': False,
            'CONNECT_TIMEOUT': 5,
        }
    
    @patch('voip.ami.socket.create_connection')
    def test_connection_success(self, mock_socket):
        """Тест успешного подключения"""
        mock_socket.return_value = Mock()
        
        client = AmiClient(self.config)
        client.connect()
        
        self.assertIsNotNone(client.socket)
        mock_socket.assert_called_once()
    
    @patch('voip.ami.socket.create_connection')
    def test_connection_failure(self, mock_socket):
        """Тест неудачного подключения"""
        mock_socket.side_effect = ConnectionError("Connection refused")
        
        client = AmiClient(self.config)
        
        with self.assertRaises(ConnectionError):
            client.connect()


class AsteriskCallControlTest(TestCase):
    """Тесты управления звонками"""
    
    def setUp(self):
        self.mock_client = Mock()
        self.control = AsteriskCallControl(self.mock_client)
    
    def test_originate_call(self):
        """Тест инициации звонка"""
        self.mock_client.send_action_sync.return_value = {
            'Response': 'Success',
            'Message': 'Originate successfully queued'
        }
        
        result = self.control.originate(
            channel='SIP/101',
            extension='1234567890'
        )
        
        self.assertEqual(result['Response'], 'Success')
        self.mock_client.send_action_sync.assert_called_once()
    
    def test_hangup_call(self):
        """Тест завершения звонка"""
        self.mock_client.send_action_sync.return_value = {
            'Response': 'Success'
        }
        
        result = self.control.hangup('SIP/101-00000001')
        
        self.assertEqual(result['Response'], 'Success')
    
    def test_transfer_call(self):
        """Тест переадресации звонка"""
        self.mock_client.send_action_sync.return_value = {
            'Response': 'Success'
        }
        
        result = self.control.transfer(
            channel='SIP/101-00000001',
            extension='102'
        )
        
        self.assertEqual(result['Response'], 'Success')


class AsteriskQueueMonitorTest(TestCase):
    """Тесты мониторинга очередей"""
    
    def setUp(self):
        self.mock_client = Mock()
        self.monitor = AsteriskQueueMonitor(self.mock_client)
    
    def test_add_queue_member(self):
        """Тест добавления агента в очередь"""
        self.mock_client.send_action_sync.return_value = {
            'Response': 'Success'
        }
        
        result = self.monitor.add_queue_member(
            queue='support',
            interface='SIP/101',
            member_name='John Doe'
        )
        
        self.assertEqual(result['Response'], 'Success')
    
    def test_pause_queue_member(self):
        """Тест постановки агента на паузу"""
        self.mock_client.send_action_sync.return_value = {
            'Response': 'Success'
        }
        
        result = self.monitor.pause_queue_member(
            queue='support',
            interface='SIP/101',
            paused=True,
            reason='Break'
        )
        
        self.assertEqual(result['Response'], 'Success')
    
    def test_get_queue_summary(self):
        """Тест получения статистики очереди"""
        # Mock данных очереди
        mock_queue_data = [{
            'queue': 'support',
            'calls': 5,
            'completed': 100,
            'abandoned': 10,
            'holdtime': 45,
            'talktime': 180,
            'members': [
                {
                    'name': 'Agent1',
                    'status': 'available',
                    'paused': False,
                    'in_call': 0,
                    'calls_taken': 50
                }
            ],
            'callers': [
                {
                    'position': 1,
                    'wait': 30,
                    'caller_id_num': '1234567890'
                }
            ]
        }]
        
        with patch.object(self.monitor, 'get_queue_status', return_value=mock_queue_data):
            summary = self.monitor.get_queue_summary('support')
            
            self.assertEqual(summary['queue'], 'support')
            self.assertEqual(summary['calls_waiting'], 5)
            self.assertEqual(summary['available_agents'], 1)


class AsteriskHealthCheckTest(TestCase):
    """Тесты проверки здоровья системы"""
    
    def setUp(self):
        self.mock_client = Mock()
        self.health = AsteriskHealthCheck(self.mock_client)
    
    def test_check_connection(self):
        """Тест проверки соединения"""
        self.mock_client.send_action_sync.return_value = {
            'Response': 'Success',
            'Ping': 'Pong'
        }
        
        result = self.health.check_connection()
        
        self.assertEqual(result['status'], 'healthy')
        self.assertTrue(result['connected'])
        self.assertIsNotNone(result['response_time'])
    
    def test_get_system_info(self):
        """Тест получения системной информации"""
        self.mock_client.send_action_sync.side_effect = [
            {
                'Response': 'Success',
                'AsteriskVersion': '20.5.0',
                'SystemName': 'pbx-server'
            },
            {
                'Response': 'Success',
                'CoreCurrentCalls': '5'
            }
        ]
        
        info = self.health.get_system_info()
        
        self.assertEqual(info['version'], '20.5.0')
        self.assertEqual(info['system'], 'pbx-server')
        self.assertEqual(info['calls_active'], 5)


# Запуск тестов
# python manage.py test tests.voip.test_asterisk_integration
```

### Integration Tests

Тесты с реальным Asterisk (требуют работающий Asterisk):

```python
from django.test import TestCase
from voip.ami import AmiClient
from voip.integrations.asterisk_control import AsteriskCallControl
from voip.utils import load_asterisk_config


class AsteriskIntegrationTest(TestCase):
    """Интеграционные тесты с реальным Asterisk"""
    
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = load_asterisk_config()
        cls.client = AmiClient(cls.config)
        cls.client.connect()
    
    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        super().tearDownClass()
    
    def test_ping_pong(self):
        """Тест ping-pong с Asterisk"""
        response = self.client.send_action_sync('Ping', timeout=5.0)
        
        self.assertEqual(response.get('Response'), 'Success')
        self.assertIn('Ping', response)
    
    def test_core_status(self):
        """Тест получения статуса ядра"""
        response = self.client.send_action_sync('CoreStatus', timeout=5.0)
        
        self.assertEqual(response.get('Response'), 'Success')
        self.assertIn('CoreCurrentCalls', response)
    
    def test_sip_peers(self):
        """Тест получения списка SIP пиров"""
        peers = []
        
        def collect_peers(responses):
            for resp in responses:
                if resp.get('Event') == 'PeerEntry':
                    peers.append(resp)
        
        self.client.send_action('SIPpeers', callback=collect_peers)
        
        import time
        time.sleep(1)  # Ждем сбора данных
        
        self.assertGreater(len(peers), 0)


# Запуск интеграционных тестов
# python manage.py test tests.voip.test_asterisk_integration.AsteriskIntegrationTest
```

### Manual Testing Checklist

#### 1. Подключение
- [ ] `python manage.py test_asterisk_connection`
- [ ] Проверить response time < 100ms
- [ ] Проверить версию Asterisk
- [ ] Проверить количество активных каналов

#### 2. Управление звонками
- [ ] Инициировать тестовый звонок
- [ ] Перевести звонок на другой номер
- [ ] Припарковать звонок
- [ ] Завершить звонок

```python
from voip.ami import AmiClient
from voip.integrations.asterisk_control import AsteriskCallControl
from voip.utils import load_asterisk_config

config = load_asterisk_config()
client = AmiClient(config)
client.connect()
control = AsteriskCallControl(client)

# Тест 1: Originate
result = control.originate('SIP/101', '100')
print(f"Originate: {result}")

# Тест 2: Получить активные каналы
channels = control.get_active_channels()
print(f"Active channels: {len(channels)}")

client.close()
```

#### 3. Очереди
- [ ] Получить статус всех очередей
- [ ] Добавить агента в очередь
- [ ] Поставить агента на паузу
- [ ] Снять агента с паузы
- [ ] Удалить агента из очереди

```bash
# CLI тесты
python manage.py asterisk_queue_stats
python manage.py asterisk_queue_stats --queue support
```

#### 4. Мониторинг
- [ ] Health check пройден
- [ ] Проверка каналов работает
- [ ] Проверка очередей работает
- [ ] Алерты генерируются корректно

```bash
python manage.py test_asterisk_connection --full
```

#### 5. CDR Импорт
- [ ] Импорт из CSV работает
- [ ] Импорт из БД работает
- [ ] Дубликаты пропускаются
- [ ] Контакты связываются корректно

```bash
python manage.py import_asterisk_cdr --source database --days 1
```

### Performance Testing

```python
import time
from voip.ami import AmiClient
from voip.utils import load_asterisk_config

config = load_asterisk_config()
client = AmiClient(config)
client.connect()

# Тест 1: Ping latency
pings = []
for i in range(100):
    start = time.time()
    client.send_action_sync('Ping', timeout=1.0)
    latency = (time.time() - start) * 1000
    pings.append(latency)

avg_latency = sum(pings) / len(pings)
max_latency = max(pings)
min_latency = min(pings)

print(f"Ping Statistics:")
print(f"  Average: {avg_latency:.2f}ms")
print(f"  Min: {min_latency:.2f}ms")
print(f"  Max: {max_latency:.2f}ms")

# Тест 2: Queue status retrieval time
from voip.integrations.asterisk_queue import AsteriskQueueMonitor

monitor = AsteriskQueueMonitor(client)

start = time.time()
queues = monitor.get_queue_status()
elapsed = (time.time() - start) * 1000

print(f"\nQueue Status Retrieval:")
print(f"  Time: {elapsed:.2f}ms")
print(f"  Queues: {len(queues)}")

client.close()
```

### Load Testing

```python
import concurrent.futures
from voip.ami import AmiClient
from voip.utils import load_asterisk_config

def ping_asterisk():
    """Одно ping соединение"""
    config = load_asterisk_config()
    client = AmiClient(config)
    try:
        client.connect()
        response = client.send_action_sync('Ping', timeout=5.0)
        client.close()
        return response.get('Response') == 'Success'
    except Exception as e:
        return False

# Нагрузочный тест: 10 параллельных подключений
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(ping_asterisk) for _ in range(10)]
    results = [f.result() for f in concurrent.futures.as_completed(futures)]

success_rate = sum(results) / len(results) * 100
print(f"Success Rate: {success_rate:.1f}%")
```

### Troubleshooting Tests

```python
def test_troubleshooting():
    """Диагностические тесты"""
    
    print("=== Asterisk Integration Diagnostics ===\n")
    
    # 1. Проверка конфигурации
    print("1. Configuration Check")
    try:
        config = load_asterisk_config()
        print(f"   ✓ Config loaded: {config['HOST']}:{config['PORT']}")
    except Exception as e:
        print(f"   ✗ Config error: {e}")
        return
    
    # 2. Проверка сети
    print("\n2. Network Check")
    import socket
    try:
        sock = socket.create_connection(
            (config['HOST'], config['PORT']),
            timeout=5
        )
        sock.close()
        print(f"   ✓ Network connection OK")
    except Exception as e:
        print(f"   ✗ Network error: {e}")
        return
    
    # 3. Проверка AMI
    print("\n3. AMI Check")
    try:
        client = AmiClient(config)
        client.connect()
        print(f"   ✓ AMI connection OK")
        
        # 4. Проверка аутентификации
        print("\n4. Authentication Check")
        response = client.send_action_sync('Ping')
        if response.get('Response') == 'Success':
            print(f"   ✓ Authentication OK")
        else:
            print(f"   ✗ Authentication failed")
        
        client.close()
    except Exception as e:
        print(f"   ✗ AMI error: {e}")
        return
    
    print("\n=== All checks passed! ===")

# Запуск
test_troubleshooting()
```

### Continuous Integration

Пример `.github/workflows/asterisk-tests.yml`:

```yaml
name: Asterisk Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      asterisk:
        image: andrius/asterisk:20
        ports:
          - 5038:5038
    
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: 3.9
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Wait for Asterisk
      run: |
        sleep 10
    
    - name: Run tests
      env:
        ASTERISK_AMI_HOST: localhost
        ASTERISK_AMI_PORT: 5038
        ASTERISK_AMI_USERNAME: admin
        ASTERISK_AMI_SECRET: admin
      run: |
        python manage.py test tests.voip.test_asterisk_integration
```

### Monitoring Tests

```python
from voip.utils.asterisk_health import AsteriskHealthCheck

def test_monitoring():
    """Тесты системы мониторинга"""
    
    config = load_asterisk_config()
    client = AmiClient(config)
    client.connect()
    
    health = AsteriskHealthCheck(client)
    
    # Проверка всех компонентов мониторинга
    tests = {
        'Connection': health.check_connection,
        'System Info': health.get_system_info,
        'Channels': health.check_channels_availability,
        'Queues': health.check_queues_health,
        'Full Report': health.get_full_health_report,
    }
    
    results = {}
    for name, test_func in tests.items():
        try:
            result = test_func()
            status = result.get('status', 'unknown')
            results[name] = status
            print(f"{name}: {status}")
        except Exception as e:
            results[name] = 'error'
            print(f"{name}: error - {e}")
    
    client.close()
    
    # Проверяем, что все тесты прошли
    all_passed = all(s in ['healthy', 'excellent', 'good'] 
                     for s in results.values())
    
    return all_passed

# Запуск
if test_monitoring():
    print("\n✓ All monitoring tests passed!")
else:
    print("\n✗ Some monitoring tests failed")
```

---

## Запуск всех тестов

```bash
# Unit tests
python manage.py test tests.voip.test_asterisk_integration

# Integration tests (требуют работающий Asterisk)
python manage.py test tests.voip.test_asterisk_integration.AsteriskIntegrationTest

# Manual tests
python manage.py test_asterisk_connection --full --queues

# Performance tests
python -c "from tests.voip.test_asterisk_performance import *; run_all_tests()"
```

## Результаты тестирования

Документируйте результаты:

```
=== Test Results ===
Date: 2024-XX-XX
Asterisk Version: 20.5.0
Django CRM Version: X.X.X

Unit Tests: PASSED (25/25)
Integration Tests: PASSED (10/10)
Performance Tests: PASSED
  - Avg Latency: 12.5ms
  - Success Rate: 100%

Manual Tests:
  ✓ Connection
  ✓ Call Control
  ✓ Queue Management
  ✓ Health Monitoring
  ✓ CDR Import

Overall: ALL TESTS PASSED ✓
```

---

**Успешного тестирования!** 🎉
