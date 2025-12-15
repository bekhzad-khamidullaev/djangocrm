# Руководство по интеграции с Asterisk PBX

## Содержание

1. [Введение](#введение)
2. [Требования](#требования)
3. [Установка и настройка Asterisk](#установка-и-настройка-asterisk)
4. [Настройка AMI](#настройка-ami)
5. [Настройка Django CRM](#настройка-django-crm)
6. [Конфигурация диалплана](#конфигурация-диалплана)
7. [Настройка очередей](#настройка-очередей)
8. [Использование API](#использование-api)
9. [Мониторинг и отладка](#мониторинг-и-отладка)
10. [Troubleshooting](#troubleshooting)

---

## Введение

Django CRM предоставляет полнофункциональную интеграцию с Asterisk PBX через Asterisk Manager Interface (AMI). Это позволяет:

- Автоматически маршрутизировать входящие звонки
- Управлять звонками (инициация, переадресация, парковка)
- Мониторить очереди и агентов
- Собирать статистику звонков (CDR)
- Отправлять уведомления о пропущенных звонках
- Интегрировать звонки с CRM записями

Сам Asterisk может быть частью стека CRM (отдельный контейнер в docker-compose или сервис на том же сервере) и управляться из системы через realtime PJSIP/Dialplan. Встроенный режим дает:
- **Полная поддержка PJSIP** с расширенными возможностями
- **Управление диалпланом** из CRM
- **Очереди и группы звонков**
- **Маршрутизация звонков и расширенные настройки**

### Архитектура интеграции

```
┌─────────────────┐      AMI        ┌──────────────────┐
│  Asterisk PBX   │◄───────────────►│   Django CRM     │
│                 │    (port 5038)   │                  │
│  - Dialplan     │                  │  - AMI Client    │
│  - Queues       │                  │  - Call Handler  │
│  - CDR          │                  │  - Queue Monitor │
└─────────────────┘                  └──────────────────┘
```

---

## Требования

### Версии ПО

- **Asterisk**: 16.x, 18.x, 20.x, 21.x (рекомендуется LTS версии)
- **Django**: 4.0+
- **Python**: 3.8+
- **База данных**: PostgreSQL 12+ или MySQL 8.0+

### Сетевые требования

- Порт **5038** (AMI) должен быть доступен между Asterisk и Django CRM
- Если используется SSL: настройте сертификаты для AMI over TLS
- Для собственной телефонии на Asterisk 21 с realtime (PostgreSQL) используйте дополнительное руководство: `ASTERISK_REALTIME_SETUP.md`

### Где размещать Asterisk
- Прод: отдельный сервер/VM рядом с провайдером связи; CRM подключается по AMI и к той же БД PostgreSQL.
- Dev/demo: можно запустить контейнер Asterisk 21 в одной сети с CRM и пробросить AMI/RTP наружу. См. пример compose фрагмента в `ASTERISK_REALTIME_SETUP.md`.

---

## Установка и настройка Asterisk

### Установка Asterisk на Ubuntu/Debian

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y build-essential wget libssl-dev libncurses5-dev \
    libnewt-dev libxml2-dev linux-headers-$(uname -r) libsqlite3-dev \
    uuid-dev libjansson-dev

# Скачивание Asterisk
cd /usr/src
sudo wget http://downloads.asterisk.org/pub/telephony/asterisk/asterisk-20-current.tar.gz
sudo tar xvf asterisk-20-current.tar.gz
cd asterisk-20*/

# Установка mp3 модулей (опционально)
sudo contrib/scripts/get_mp3_source.sh

# Конфигурация и компиляция
sudo ./configure
sudo make menuselect  # Выберите необходимые модули
sudo make -j$(nproc)
sudo make install
sudo make samples    # Создать примеры конфигурации
sudo make config     # Создать systemd сервис

# Создание пользователя
sudo useradd -r -d /var/lib/asterisk -s /sbin/nologin asterisk
sudo chown -R asterisk:asterisk /etc/asterisk /var/lib/asterisk \
    /var/log/asterisk /var/spool/asterisk /usr/lib/asterisk

# Запуск
sudo systemctl start asterisk
sudo systemctl enable asterisk
```

### Установка Asterisk на CentOS/RHEL

```bash
# Установка репозитория EPEL
sudo yum install -y epel-release

# Установка зависимостей
sudo yum groupinstall -y "Development Tools"
sudo yum install -y wget ncurses-devel libxml2-devel sqlite-devel \
    libuuid-devel jansson-devel

# Далее аналогично Ubuntu
```

---

## Настройка AMI

### 1. Создание AMI пользователя

Отредактируйте `/etc/asterisk/manager.conf`:

```ini
[general]
enabled = yes
port = 5038
bindaddr = 0.0.0.0  ; Или конкретный IP для безопасности

; SSL настройки (опционально)
;tlsenable=yes
;tlsbindaddr=0.0.0.0:5039
;tlscertfile=/etc/asterisk/keys/asterisk.pem
;tlsprivatekey=/etc/asterisk/keys/asterisk.key

[django_crm]
secret = YourSecurePasswordHere123!
deny = 0.0.0.0/0.0.0.0
permit = 192.168.1.0/255.255.255.0  ; IP адрес Django сервера
;permit = 10.0.0.50/255.255.255.255  ; Конкретный IP

; Разрешения для Django CRM
read = system,call,log,verbose,agent,user,config,command,dtmf,reporting,cdr,dialplan,originate,message
write = system,call,log,verbose,agent,user,config,command,dtmf,reporting,cdr,dialplan,originate,message

; Минимальные разрешения для базовой интеграции
;read = call,agent,user,originate
;write = call,originate,redirect
```

### 2. Безопасность AMI

**Важно!** AMI предоставляет полный контроль над Asterisk. Соблюдайте меры безопасности:

```ini
[general]
enabled = yes
port = 5038
bindaddr = 127.0.0.1  ; Только локальные подключения

; Включить webenabled только если нужно
webenabled = no

; Настройка таймаутов
authtimeout = 30
authlimit = 50
```

### 3. Перезагрузка конфигурации

```bash
sudo asterisk -rx "manager reload"
# или
sudo systemctl restart asterisk
```

### 4. Проверка AMI соединения

```bash
# Подключение к AMI через telnet
telnet localhost 5038

# Или используйте netcat
nc localhost 5038
```

Вы должны увидеть приветствие:
```
Asterisk Call Manager/2.10.0
```

Для входа отправьте:
```
Action: Login
Username: django_crm
Secret: YourSecurePasswordHere123!

```

---

## Настройка Django CRM

### 1. Настройка в settings.py

Добавьте в ваш `settings.py` или создайте `settings/voip.py`:

```python
# Asterisk AMI Configuration
ASTERISK_AMI = {
    'HOST': '192.168.1.100',  # IP адрес Asterisk сервера
    'PORT': 5038,
    'USERNAME': 'django_crm',
    'SECRET': 'YourSecurePasswordHere123!',
    'USE_SSL': False,  # True если используете AMI over TLS
    'CONNECT_TIMEOUT': 5,
    'RECONNECT_DELAY': 5,
    'DEBUG_MODE': False,  # True для детального логирования
}

# CDR Import Configuration (опционально)
ASTERISK_CDR = {
    'ENABLED': True,
    'IMPORT_INTERVAL': 300,  # секунды (5 минут)
    'DB_CONFIG': {
        'host': '192.168.1.100',
        'user': 'asteriskcdr',
        'password': 'cdr_password',
        'database': 'asteriskcdrdb',
    }
}

# Настройки логирования
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django-crm/asterisk.log',
        },
    },
    'loggers': {
        'voip.integrations.asterisk': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
        'voip.ami': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}
```

### 2. Применение миграций

```bash
python manage.py migrate voip
```

### 3. Создание VoIP настроек в админке

1. Перейдите в Django Admin → VoIP → VoIP Settings
2. Заполните поля:
   - **AMI Host**: IP адрес Asterisk
   - **AMI Port**: 5038
   - **AMI Username**: django_crm
   - **AMI Secret**: ваш пароль
   - **AMI over SSL**: отметьте если используете TLS

### 4. Тестирование подключения

```bash
# Тест подключения к Asterisk
python manage.py test_asterisk_connection

# Полная проверка с очередями
python manage.py test_asterisk_connection --full --queues
```

Вы должны увидеть:
```
Testing Asterisk AMI Connection
================================
Host: 192.168.1.100
Port: 5038
Username: django_crm
SSL: False

Connecting to Asterisk AMI... OK

Connection Test
===============
✓ Connected (response time: 15.3ms)

System Information
==================
Version: Asterisk 20.5.0
System: pbx-server
Active calls: 0

Connection test completed successfully
```

---

## Конфигурация диалплана

### Базовая конфигурация extensions.conf

```ini
[globals]
; Глобальные переменные
DJANGO_CRM_API=http://192.168.1.50:8000/api/voip
DJANGO_CRM_TOKEN=your-api-token-here

[from-external]
; Контекст для входящих звонков
exten => _X.,1,NoOp(Incoming call from ${CALLERID(num)} to ${EXTEN})
    same => n,Set(CHANNEL(language)=ru)
    same => n,Set(__DYNAMIC_FEATURES=automon)
    
    ; Уведомление Django CRM о входящем звонке
    same => n,Set(CRM_CONTACT=${CURL(${DJANGO_CRM_API}/lookup/${CALLERID(num)})})
    same => n,NoOp(CRM Contact: ${CRM_CONTACT})
    
    ; Маршрутизация через Django CRM
    same => n,Set(ROUTE_TARGET=${CURL(${DJANGO_CRM_API}/route/${CALLERID(num)}/${EXTEN})})
    same => n,GotoIf($["${ROUTE_TARGET}" != ""]?route:default)
    
    same => n(route),Dial(SIP/${ROUTE_TARGET},30,tT)
    same => n,Goto(after-dial,1)
    
    same => n(default),Goto(default-handler,1)
    
    same => n(after-dial),NoOp(Call ended: ${DIALSTATUS})
    same => n,Hangup()

[default-handler]
; Обработчик по умолчанию
exten => 1,1,NoOp(Default handler)
    same => n,Answer()
    same => n,Playback(welcome)
    same => n,Queue(support,t,,,300)
    same => n,Voicemail(100@default,u)
    same => n,Hangup()

[internal]
; Контекст для внутренних звонков
exten => _1XX,1,NoOp(Internal call to ${EXTEN})
    same => n,Dial(SIP/${EXTEN},20,tT)
    same => n,Voicemail(${EXTEN}@default,u)
    same => n,Hangup()

[outbound]
; Контекст для исходящих звонков
exten => _NXXNXXXXXX,1,NoOp(Outbound call to ${EXTEN})
    same => n,Set(CALLERID(num)=+1234567890)  ; Ваш исходящий номер
    same => n,Dial(SIP/provider/${EXTEN},60,tT)
    same => n,Hangup()

; Парковка звонков
[parkedcalls]
exten => 700,1,Park()

; Конференции
[conferences]
exten => 8000,1,ConfBridge(8000)
```

### Интеграция с Django CRM через AGI

Создайте AGI скрипт `/var/lib/asterisk/agi-bin/django_crm_route.py`:

```python
#!/usr/bin/env python3
import sys
import requests

def agi_response(command):
    """Отправить команду AGI"""
    print(command)
    sys.stdout.flush()
    return sys.stdin.readline().strip()

def main():
    # Читаем AGI переменные
    agi_vars = {}
    while True:
        line = sys.stdin.readline().strip()
        if not line:
            break
        key, value = line.split(':', 1)
        agi_vars[key.strip()] = value.strip()
    
    caller_id = agi_vars.get('agi_callerid', '')
    extension = agi_vars.get('agi_extension', '')
    
    # Запрос маршрутизации к Django CRM
    try:
        response = requests.get(
            f'http://192.168.1.50:8000/api/voip/route/{caller_id}/{extension}',
            headers={'Authorization': 'Token your-api-token'},
            timeout=2
        )
        
        if response.status_code == 200:
            data = response.json()
            target = data.get('target', '')
            
            if target:
                agi_response(f'SET VARIABLE ROUTE_TARGET {target}')
                agi_response('VERBOSE "Routed to: {}" 1'.format(target))
        
    except Exception as e:
        agi_response(f'VERBOSE "Routing error: {e}" 1')

if __name__ == '__main__':
    main()
```

Сделайте скрипт исполняемым:
```bash
sudo chmod +x /var/lib/asterisk/agi-bin/django_crm_route.py
sudo chown asterisk:asterisk /var/lib/asterisk/agi-bin/django_crm_route.py
```

Использование в диалплане:
```ini
[from-external]
exten => _X.,1,AGI(django_crm_route.py)
    same => n,GotoIf($["${ROUTE_TARGET}" != ""]?route:default)
    same => n(route),Dial(SIP/${ROUTE_TARGET},30)
    same => n(default),Queue(support)
    same => n,Hangup()
```

---

## Настройка очередей

### Конфигурация queues.conf

```ini
[general]
persistentmembers = yes
autofill = yes
monitor-type = MixMonitor

[support]
; Очередь поддержки
strategy = rrmemory  ; Round-robin с памятью
timeout = 20
retry = 5
maxlen = 50
announce-frequency = 30
announce-holdtime = yes
announce-position = yes

; Музыка на удержании
musicclass = default

; Service Level Agreement
servicelevel = 60
; Алерт если более 80% звонков не отвечены за 60 секунд

; Члены очереди (динамически управляются через Django CRM)
;member => SIP/101,1,Agent 1,hint:101@internal
;member => SIP/102,1,Agent 2,hint:102@internal

; Опции записи
monitor-format = wav
monitor-type = MixMonitor

[sales]
; Очередь продаж
strategy = fewestcalls
timeout = 30
retry = 10
maxlen = 100
weight = 10  ; Приоритет выше чем у support

announce-frequency = 60
periodic-announce = queue-periodic-announce
periodic-announce-frequency = 60

servicelevel = 30

[vip]
; VIP очередь
strategy = ringall
timeout = 15
retry = 3
maxlen = 20
weight = 20  ; Наивысший приоритет

announce-holdtime = yes
announce-position = no  ; Не объявляем позицию VIP клиентам
```

### Стратегии распределения

- **ringall**: Звонит всем агентам одновременно
- **leastrecent**: Агенту, который дольше всех не принимал звонок
- **fewestcalls**: Агенту с наименьшим количеством принятых звонков
- **random**: Случайный агент
- **rrmemory**: Round-robin с памятью последнего агента
- **linear**: По порядку (используется penalty)
- **wrandom**: Взвешенный случайный выбор

### Управление агентами через Django CRM

```python
from voip.ami import AmiClient
from voip.integrations.asterisk_queue import AsteriskQueueMonitor
from voip.utils import load_asterisk_config

# Подключение к Asterisk
config = load_asterisk_config()
client = AmiClient(config)
client.connect()

monitor = AsteriskQueueMonitor(client)

# Добавить агента в очередь
monitor.add_queue_member(
    queue='support',
    interface='SIP/101',
    member_name='John Doe',
    penalty=0
)

# Удалить агента из очереди
monitor.remove_queue_member(
    queue='support',
    interface='SIP/101'
)

# Поставить агента на паузу
monitor.pause_queue_member(
    queue='support',
    interface='SIP/101',
    paused=True,
    reason='Break'
)

# Получить статистику очереди
summary = monitor.get_queue_summary('support')
print(f"Calls waiting: {summary['calls_waiting']}")
print(f"Available agents: {summary['available_agents']}")

client.close()
```

---

## Использование API

### Управление звонками

```python
from voip.ami import AmiClient
from voip.integrations.asterisk_control import AsteriskCallControl
from voip.utils import load_asterisk_config

# Подключение
config = load_asterisk_config()
client = AmiClient(config)
client.connect()

control = AsteriskCallControl(client)

# Инициировать звонок
control.originate(
    channel='SIP/101',
    extension='1234567890',
    context='outbound',
    caller_id='Company Name <+1234567890>'
)

# Перевести звонок
control.transfer(
    channel='SIP/101-00000001',
    extension='102',
    context='internal'
)

# Припарковать звонок
result = control.park(
    channel='SIP/101-00000001',
    parking_lot='default'
)
print(f"Parked at: {result.get('ParkingSpace')}")

# Завершить звонок
control.hangup(channel='SIP/101-00000001')

client.close()
```

### Мониторинг здоровья системы

```python
from voip.ami import AmiClient
from voip.utils.asterisk_health import AsteriskHealthCheck
from voip.utils import load_asterisk_config

config = load_asterisk_config()
client = AmiClient(config)
client.connect()

health = AsteriskHealthCheck(client)

# Полная проверка
report = health.get_full_health_report()

print(f"Overall Status: {report['overall_status']}")
print(f"Active Channels: {report['checks']['channels']['active_channels']}")
print(f"SIP Peers Online: {report['checks']['channels']['sip_peers']['online']}")

# Проверка качества звонков
quality = health.monitor_call_quality(threshold_seconds=3600)
print(f"Completion Rate: {quality['completed_calls']}/{quality['total_calls']}")
print(f"Average Duration: {quality['avg_duration']}s")

client.close()
```

### Импорт CDR

```python
from voip.utils.cdr_import import AsteriskCDRImporter

importer = AsteriskCDRImporter()

# Импорт из CSV
result = importer.import_from_csv('/var/log/asterisk/cdr-csv/Master.csv')

print(f"Imported: {result['imported']}")
print(f"Skipped: {result['skipped']}")
print(f"Errors: {result['errors']}")

# Импорт из базы данных
db_config = {
    'host': '192.168.1.100',
    'user': 'asteriskcdr',
    'password': 'cdr_password',
    'database': 'asteriskcdrdb',
}

from datetime import datetime, timedelta
end_date = datetime.now()
start_date = end_date - timedelta(days=7)

result = importer.import_from_database(db_config, start_date, end_date)
```

---

## Мониторинг и отладка

### Django management команды

```bash
# Тест подключения
python manage.py test_asterisk_connection

# Полная проверка с деталями
python manage.py test_asterisk_connection --full --queues

# Статистика очередей
python manage.py asterisk_queue_stats

# Статистика конкретной очереди
python manage.py asterisk_queue_stats --queue support

# Мониторинг в реальном времени
python manage.py asterisk_queue_stats --watch

# Импорт CDR
python manage.py import_asterisk_cdr --source database --days 7

# Импорт из CSV
python manage.py import_asterisk_cdr --source csv --file /path/to/Master.csv
```

### Логи Asterisk

```bash
# Основной лог
tail -f /var/log/asterisk/messages

# Полный лог
tail -f /var/log/asterisk/full

# CDR лог
tail -f /var/log/asterisk/cdr-csv/Master.csv

# Queue лог
tail -f /var/log/asterisk/queue_log

# Логи Django CRM
tail -f /var/log/django-crm/asterisk.log
```

### Asterisk CLI команды

```bash
# Подключение к CLI
sudo asterisk -rvvv

# Проверка AMI
manager show connected

# Статус каналов
core show channels

# Статус очередей
queue show

# Статус конкретной очереди
queue show support

# SIP пиры
sip show peers

# Перезагрузка модулей
module reload app_queue.so
manager reload
```

---

## Troubleshooting

### Проблема: Не удается подключиться к AMI

**Симптомы:**
```
ConnectionError: Failed to connect to Asterisk AMI
```

**Решение:**
1. Проверьте, что Asterisk запущен:
   ```bash
   sudo systemctl status asterisk
   ```

2. Проверьте, что AMI включен:
   ```bash
   sudo asterisk -rx "manager show settings"
   ```

3. Проверьте firewall:
   ```bash
   sudo ufw allow 5038/tcp
   # или
   sudo firewall-cmd --add-port=5038/tcp --permanent
   sudo firewall-cmd --reload
   ```

4. Проверьте bind address в `/etc/asterisk/manager.conf`:
   ```ini
   bindaddr = 0.0.0.0  ; Не 127.0.0.1
   ```

### Проблема: Ошибка аутентификации

**Симптомы:**
```
Authentication failed: Invalid username or password
```

**Решение:**
1. Проверьте учетные данные в `/etc/asterisk/manager.conf`
2. Проверьте permit/deny правила:
   ```ini
   [django_crm]
   secret = correct_password
   deny = 0.0.0.0/0.0.0.0
   permit = 192.168.1.50/255.255.255.255  ; IP Django сервера
   ```

3. Перезагрузите конфигурацию:
   ```bash
   sudo asterisk -rx "manager reload"
   ```

### Проблема: События не приходят

**Симптомы:**
Подключение работает, но события звонков не обрабатываются.

**Решение:**
1. Проверьте права на чтение событий:
   ```ini
   [django_crm]
   read = call,agent,user,cdr,dialplan
   ```

2. Проверьте, что события включены при логине:
   ```python
   login_action = (
       f"Action: Login\r\n"
       f"Username: {self.username}\r\n"
       f"Secret: {self.secret}\r\n"
       f"Events: call,agent,queue\r\n"  # ← Важно!
       f"\r\n"
   )
   ```

3. Включите debug логирование:
   ```python
   ASTERISK_AMI = {
       # ...
       'DEBUG_MODE': True,
   }
   ```

### Проблема: Звонки не маршрутизируются

**Симптомы:**
Звонки приходят, но не перенаправляются на нужных агентов.

**Решение:**
1. Проверьте диалплан:
   ```bash
   sudo asterisk -rx "dialplan show from-external"
   ```

2. Проверьте контекст в `extensions.conf`:
   ```ini
   [from-external]
   exten => _X.,1,NoOp(Incoming call)
       same => n,Goto(internal,${ROUTE_TARGET},1)  ; ← Правильный контекст
   ```

3. Проверьте права на Redirect action:
   ```ini
   [django_crm]
   write = call,redirect,originate
   ```

### Проблема: Высокая задержка или таймауты

**Симптомы:**
```
TimeoutError: AMI action timed out after 5.0s
```

**Решение:**
1. Увеличьте таймауты:
   ```python
   ASTERISK_AMI = {
       # ...
       'CONNECT_TIMEOUT': 10,
   }
   ```

2. Проверьте сетевую задержку:
   ```bash
   ping -c 10 192.168.1.100
   ```

3. Проверьте нагрузку на Asterisk:
   ```bash
   sudo asterisk -rx "core show sysinfo"
   top -p $(pidof asterisk)
   ```

### Проблема: CDR не импортируются

**Симптомы:**
```
Error importing CDR: Access denied
```

**Решение:**
1. Проверьте права доступа к базе CDR:
   ```sql
   GRANT SELECT ON asteriskcdrdb.* TO 'asteriskcdr'@'192.168.1.50';
   FLUSH PRIVILEGES;
   ```

2. Установите pymysql:
   ```bash
   pip install pymysql
   ```

3. Проверьте настройки:
   ```python
   ASTERISK_CDR = {
       'DB_CONFIG': {
           'host': '192.168.1.100',
           'user': 'asteriskcdr',
           'password': 'correct_password',
           'database': 'asteriskcdrdb',
       }
   }
   ```

---

## Дополнительные ресурсы

### Документация

- [Asterisk Wiki](https://wiki.asterisk.org/)
- [AMI Documentation](https://wiki.asterisk.org/wiki/display/AST/Asterisk+Manager+Interface+%28AMI%29)
- [Dialplan Functions](https://wiki.asterisk.org/wiki/display/AST/Dialplan+Functions)
- [Queue Documentation](https://wiki.asterisk.org/wiki/display/AST/Queues)

### Примеры конфигураций

Примеры конфигурационных файлов доступны в:
- `/etc/asterisk/*.conf.sample`
- [Asterisk Config Examples](https://github.com/asterisk/asterisk/tree/master/configs/samples)

### Сообщество

- [Asterisk Forum](https://community.asterisk.org/)
- [Asterisk Users Mailing List](http://lists.digium.com/mailman/listinfo/asterisk-users)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/asterisk)

---

## Заключение

Эта интеграция предоставляет полный контроль над Asterisk PBX из Django CRM. Для дополнительной помощи обращайтесь к документации или сообществу.

**Следующие шаги:**

1. ✅ Настроить AMI подключение
2. ✅ Протестировать базовые функции
3. ✅ Настроить маршрутизацию звонков
4. ✅ Настроить очереди и агентов
5. ✅ Настроить CDR импорт
6. ✅ Настроить мониторинг и уведомления
7. 🔄 Оптимизировать диалплан под ваши нужды

Удачи в использовании Django CRM с Asterisk! 🎉
