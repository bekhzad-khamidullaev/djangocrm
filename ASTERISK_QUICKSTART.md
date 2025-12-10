# 🚀 Asterisk Real-time Quick Start Guide

Быстрая установка и настройка Asterisk интеграции с Django CRM.

## ⚡ Быстрый старт (5 минут)

### 1. Установите Asterisk

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y asterisk asterisk-modules asterisk-config

# Или скомпилируйте последнюю версию (рекомендуется)
# См. ASTERISK_REALTIME_SETUP.md для детальной инструкции
```

### 2. Настройте базу данных

Добавьте в `.env`:

```bash
# Используйте ту же БД что и Django CRM
ASTERISK_DB_NAME=djangocrm
ASTERISK_DB_USER=crmuser
ASTERISK_DB_PASSWORD=your_password

# Или создайте отдельную БД (рекомендуется)
ASTERISK_DB_NAME=asterisk
ASTERISK_DB_USER=asteriskuser
ASTERISK_DB_PASSWORD=secure_password

# AMI настройки
ASTERISK_AMI_HOST=127.0.0.1
ASTERISK_AMI_PORT=5038
ASTERISK_AMI_USERNAME=admin
ASTERISK_AMI_SECRET=your_ami_secret

# Базовые настройки
ASTERISK_DEFAULT_CONTEXT=from-internal
ASTERISK_EXTERNAL_IP=YOUR_PUBLIC_IP
ASTERISK_CODECS=ulaw,alaw,gsm,g722
```

### 3. Примените миграции

```bash
# Применить к основной БД
python manage.py migrate

# Применить к БД Asterisk (если отдельная)
python manage.py migrate --database=asterisk
```

### 4. Настройте Asterisk

#### 4.1 Создайте `/etc/asterisk/res_config_pgsql.conf`:

```ini
[general]
dbhost = localhost
dbport = 5432
dbname = asterisk
dbuser = asteriskuser
dbpass = secure_password
```

#### 4.2 Создайте `/etc/asterisk/extconfig.conf`:

```ini
[settings]
ps_endpoints => pgsql,general,ps_endpoints
ps_auths => pgsql,general,ps_auths
ps_aors => pgsql,general,ps_aors
ps_contacts => pgsql,general,ps_contacts
ps_endpoint_id_ips => pgsql,general,ps_endpoint_id_ips
ps_transports => pgsql,general,ps_transports
extensions => pgsql,general,extensions
```

#### 4.3 Настройте AMI в `/etc/asterisk/manager.conf`:

```ini
[general]
enabled = yes
port = 5038
bindaddr = 0.0.0.0

[admin]
secret = your_ami_secret
permit = 127.0.0.1/255.255.255.0
read = all
write = all
```

#### 4.4 Базовый PJSIP в `/etc/asterisk/pjsip.conf`:

```ini
[global]
type=global

[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060
```

### 5. Запустите настройку

```bash
# Перезапустите Asterisk
sudo systemctl restart asterisk

# Проверьте подключение
python manage.py setup_asterisk_realtime --test-connection

# Создайте транспорты
python manage.py setup_asterisk_realtime --create-transports

# Auto-provision пользователей
python manage.py setup_asterisk_realtime --provision-users
```

### 6. Проверьте результат

```bash
# В Asterisk CLI
sudo asterisk -rx "pjsip show endpoints"
sudo asterisk -rx "database show"

# В Django
python manage.py shell
>>> from voip.models import PsEndpoint
>>> PsEndpoint.objects.using('asterisk').count()
10  # Количество созданных endpoints
```

## 📱 Тестирование

### Настройте SIP клиент (например, Zoiper)

1. **Server**: your_server_ip:5060
2. **Username**: 1000 (или другой созданный extension)
3. **Password**: (найдите в Django Admin > VOIP > PJSIP Auth)
4. **Transport**: UDP

### Выполните тестовый звонок

```bash
# Через Asterisk CLI
sudo asterisk -rx "originate PJSIP/1000 application Playback demo-congrats"

# Через Django
python manage.py shell
>>> from voip.backends.asteriskbackend import AsteriskRealtimeAPI
>>> from django.conf import settings
>>> config = next(b for b in settings.VOIP if b['PROVIDER'] == 'Asterisk')
>>> api = AsteriskRealtimeAPI(**config['OPTIONS'])
>>> api.originate_call('1000', '1001')
```

## 🎯 Основные команды

```bash
# Создать 10 тестовых endpoints (1000-1009)
python manage.py setup_asterisk_realtime --create-test-endpoints 10

# Синхронизировать InternalNumber с Asterisk
python manage.py setup_asterisk_realtime --sync-internal-numbers

# Валидация конфигурации
python manage.py setup_asterisk_realtime --validate

# Проверка соединения
python manage.py setup_asterisk_realtime --test-connection
```

## 🔧 Управление через Django Admin

1. Откройте **Django Admin**
2. Перейдите в раздел **VOIP**
3. Доступные разделы:
   - **PJSIP Endpoints** - управление SIP endpoints
   - **PJSIP Auth** - аутентификация
   - **PJSIP AORs** - Address of Records
   - **PJSIP Contacts** - активные регистрации
   - **PJSIP Transports** - транспорты (UDP/TCP/WSS)
   - **Dialplan Extensions** - правила маршрутизации

## 📚 Примеры кода

### Auto-provision пользователя

```python
from voip.utils.asterisk_realtime import auto_provision_endpoint
from django.contrib.auth.models import User

user = User.objects.get(username='john')
result = auto_provision_endpoint(user)

print(f"Extension: {result['endpoint_id']}")
print(f"Password: {result['password']}")
```

### Инициировать звонок

```python
from voip.backends.asteriskbackend import AsteriskRealtimeAPI
from django.conf import settings

config = next(b for b in settings.VOIP if b['PROVIDER'] == 'Asterisk')
api = AsteriskRealtimeAPI(**config['OPTIONS'])

# Позвонить с 1000 на 1001
api.originate_call('1000', '1001')
```

### Записать разговор

```python
# Начать запись
api.start_recording(
    channel='PJSIP/1000-00000001',
    filename='call-001'
)

# Остановить запись
api.stop_recording(channel='PJSIP/1000-00000001')
```

### Работа с очередями

```python
# Добавить в очередь
api.add_queue_member(
    queue='support',
    interface='PJSIP/1000',
    member_name='John Doe'
)

# Проверить статус
status = api.get_queue_status('support')
print(status)
```

## ⚠️ Устранение проблем

### Asterisk не видит endpoints

```bash
# Проверьте подключение к БД
sudo -u asterisk psql -h localhost -U asteriskuser -d asterisk

# Проверьте логи
sudo tail -f /var/log/asterisk/full

# Перезагрузите модули
sudo asterisk -rx "module reload res_pjsip.so"
sudo asterisk -rx "module reload res_config_pgsql.so"
```

### AMI не подключается

```bash
# Проверьте порт
netstat -tlnp | grep 5038

# Проверьте настройки
sudo cat /etc/asterisk/manager.conf

# Тест подключения
telnet localhost 5038
```

### Endpoints не регистрируются

```bash
# Включите debug
sudo asterisk -rx "pjsip set logger on"

# Проверьте registrations
sudo asterisk -rx "pjsip show registrations"

# Проверьте contacts
sudo asterisk -rx "pjsip show contacts"
```

## 📖 Полная документация

- **[ASTERISK_REALTIME_SETUP.md](ASTERISK_REALTIME_SETUP.md)** - Подробное руководство
- **[voip/README.md](voip/README.md)** - VoIP модуль
- **[.env.asterisk.example](.env.asterisk.example)** - Все доступные настройки

## 🆘 Поддержка

Если возникли проблемы:

1. Проверьте логи: `/var/log/asterisk/full`
2. Включите verbose: `asterisk -rx "core set verbose 5"`
3. Запустите валидацию: `python manage.py setup_asterisk_realtime --validate`
4. Проверьте конфигурацию: `asterisk -rx "pjsip show settings"`

## ✅ Контрольный список

- [ ] Asterisk установлен и запущен
- [ ] PostgreSQL/MySQL настроен
- [ ] База данных создана
- [ ] Миграции применены
- [ ] Asterisk конфигурация создана (extconfig.conf, res_config_pgsql.conf, manager.conf)
- [ ] AMI настроен и доступен
- [ ] Транспорты созданы
- [ ] Endpoints созданы
- [ ] Тестовый звонок работает

## 🎉 Готово!

Теперь вы можете:
- Создавать SIP endpoints через Django Admin
- Управлять звонками через API
- Записывать разговоры
- Использовать очереди
- Интегрировать с CRM

---

**Следующие шаги:**
1. Настройте внешние линии для исходящих звонков
2. Настройте IVR для входящих звонков
3. Интегрируйте с маршрутизацией CRM
4. Настройте запись разговоров
5. Настройте отчеты и аналитику
