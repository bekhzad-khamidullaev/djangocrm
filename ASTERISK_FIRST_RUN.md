# 🎬 Первый запуск Asterisk Real-time

Пошаговая инструкция для первого запуска интеграции Asterisk с Django CRM.

## Шаг 1: Подготовка базы данных

### Вариант А: Использовать основную БД Django CRM (проще)

Не требуется дополнительных действий - Asterisk будет использовать ту же БД.

### Вариант Б: Создать отдельную БД (рекомендуется)

```bash
# PostgreSQL
sudo -u postgres createdb asterisk
sudo -u postgres createuser asteriskuser
sudo -u postgres psql << EOF
ALTER USER asteriskuser WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE asterisk TO asteriskuser;
\c asterisk
GRANT ALL ON SCHEMA public TO asteriskuser;
EOF

# Добавьте в .env
echo "ASTERISK_DB_NAME=asterisk" >> .env
echo "ASTERISK_DB_USER=asteriskuser" >> .env
echo "ASTERISK_DB_PASSWORD=secure_password" >> .env
echo "ASTERISK_DB_HOST=localhost" >> .env
echo "ASTERISK_DB_PORT=5432" >> .env
```

## Шаг 2: Применение миграций

```bash
# Убедитесь что основная БД актуальна
python manage.py migrate

# Примените миграции к БД Asterisk
python manage.py migrate --database=asterisk

# Проверка
python manage.py shell
>>> from voip.models import PsEndpoint
>>> PsEndpoint.objects.using('asterisk').model._meta.db_table
'ps_endpoints'
>>> exit()
```

## Шаг 3: Настройка Asterisk конфигурации

### 3.1 Подключение к PostgreSQL

Создайте `/etc/asterisk/res_config_pgsql.conf`:

```bash
sudo tee /etc/asterisk/res_config_pgsql.conf > /dev/null << 'EOF'
[general]
dbhost = localhost
dbport = 5432
dbname = asterisk
dbuser = asteriskuser
dbpass = secure_password
requirements = warn
EOF
```

### 3.2 Настройка Real-time mapping

Создайте `/etc/asterisk/extconfig.conf`:

```bash
sudo tee /etc/asterisk/extconfig.conf > /dev/null << 'EOF'
[settings]
; PJSIP Real-time configuration
ps_endpoints => pgsql,general,ps_endpoints
ps_auths => pgsql,general,ps_auths
ps_aors => pgsql,general,ps_aors
ps_contacts => pgsql,general,ps_contacts
ps_endpoint_id_ips => pgsql,general,ps_endpoint_id_ips
ps_transports => pgsql,general,ps_transports

; Dialplan Real-time
extensions => pgsql,general,extensions
EOF
```

### 3.3 Настройка AMI

Создайте или обновите `/etc/asterisk/manager.conf`:

```bash
sudo tee /etc/asterisk/manager.conf > /dev/null << 'EOF'
[general]
enabled = yes
port = 5038
bindaddr = 0.0.0.0

[admin]
secret = MySecretAMIPassword123
deny = 0.0.0.0/0.0.0.0
permit = 127.0.0.1/255.255.255.255
permit = 192.168.0.0/255.255.0.0
read = all
write = all
EOF
```

Добавьте в `.env`:

```bash
echo "ASTERISK_AMI_SECRET=MySecretAMIPassword123" >> .env
```

### 3.4 Базовая конфигурация PJSIP

Создайте `/etc/asterisk/pjsip.conf`:

```bash
sudo tee /etc/asterisk/pjsip.conf > /dev/null << 'EOF'
[global]
type=global
max_forwards=70
keep_alive_interval=90
endpoint_identifier_order=ip,username,anonymous

; Базовый UDP транспорт (будет дополнен из БД)
[transport-udp]
type=transport
protocol=udp
bind=0.0.0.0:5060
EOF
```

### 3.5 Включение модулей

Проверьте `/etc/asterisk/modules.conf`:

```bash
# Убедитесь что загружены:
# load => res_pjsip.so
# load => res_config_pgsql.so
# load => manager.so
```

## Шаг 4: Перезапуск Asterisk

```bash
# Перезапустите Asterisk
sudo systemctl restart asterisk

# Проверьте статус
sudo systemctl status asterisk

# Подключитесь к CLI
sudo asterisk -rvvv

# В CLI проверьте модули:
CLI> module show like pjsip
CLI> module show like config
CLI> database show

# Выход из CLI: Ctrl+C
```

## Шаг 5: Первоначальная настройка через Django

```bash
# Проверьте подключение
python manage.py setup_asterisk_realtime --test-connection

# Ожидаемый вывод:
# ✓ Database connection OK (0 endpoints found)
# ✓ AMI connection OK (Asterisk 20.x.x)
```

## Шаг 6: Создание транспортов

```bash
python manage.py setup_asterisk_realtime --create-transports

# Проверка в Asterisk:
sudo asterisk -rx "pjsip show transports"
```

## Шаг 7: Создание тестовых endpoints

```bash
# Создайте 5 тестовых endpoints
python manage.py setup_asterisk_realtime --create-test-endpoints 5

# Проверка
sudo asterisk -rx "pjsip show endpoints"
sudo asterisk -rx "pjsip show auths"
sudo asterisk -rx "pjsip show aors"
```

Вы получите вывод с credentials, например:
```
✓ Created test endpoint 1000 (password: Xy9Kp2mN4vB8qR1w)
✓ Created test endpoint 1001 (password: Lm3Np5sT7xC9zW2a)
...
```

**Сохраните эти пароли** - они понадобятся для настройки SIP клиентов.

## Шаг 8: Настройка SIP клиента

Используйте любой SIP клиент (Zoiper, Linphone, X-Lite, MicroSIP):

**Настройки для endpoint 1000:**
- **SIP Server**: `ваш_сервер_ip` или `localhost`
- **Port**: `5060`
- **Username**: `1000`
- **Password**: `(из вывода команды выше)`
- **Transport**: `UDP`
- **Display Name**: `Test 1000`

## Шаг 9: Первый тестовый звонок

### Через Asterisk CLI:

```bash
sudo asterisk -rx "originate PJSIP/1000 application Playback demo-congrats"
```

Если endpoint 1000 зарегистрирован, он начнет звонить.

### Через Django shell:

```python
python manage.py shell

from voip.backends.asteriskbackend import AsteriskRealtimeAPI
from django.conf import settings

config = next(b for b in settings.VOIP if b['PROVIDER'] == 'Asterisk')
api = AsteriskRealtimeAPI(**config['OPTIONS'])

# Тест соединения
result = api.test_connection()
print(result)

# Позвонить с 1000 на 1001
result = api.originate_call('1000', '1001')
print(result)
```

## Шаг 10: Auto-provisioning для реальных пользователей

```bash
# Создайте endpoints для всех активных пользователей
python manage.py setup_asterisk_realtime --provision-users

# Или для конкретного пользователя через shell
python manage.py shell

from voip.utils.asterisk_realtime import auto_provision_endpoint
from django.contrib.auth.models import User

user = User.objects.get(username='admin')
result = auto_provision_endpoint(user)

print(f"Extension: {result['endpoint_id']}")
print(f"Password: {result['password']}")
print(f"SIP URI: {result['sip_uri']}")
```

## Шаг 11: Проверка через Django Admin

1. Откройте **http://localhost:8000/admin/**
2. Перейдите в **VOIP > PJSIP Endpoints**
3. Вы должны увидеть созданные endpoints со статусом регистрации
4. Попробуйте actions:
   - **Test registration** - проверить статус
   - **Reload PJSIP config** - перезагрузить конфигурацию

## 🎉 Поздравляем! Система работает!

### Что дальше?

1. **Настройте внешние линии** для исходящих звонков
2. **Создайте IVR меню** для входящих
3. **Настройте очереди** для отделов
4. **Интегрируйте с CRM** - автоматические звонки из карточек клиентов
5. **Настройте запись разговоров**
6. **Создайте отчеты** по звонкам

---

## 🔍 Проверка работоспособности

### Checklist:

- [ ] Миграции применены (`migrate --database=asterisk`)
- [ ] Asterisk подключается к БД (`database show` в CLI)
- [ ] AMI доступен (`telnet localhost 5038`)
- [ ] Транспорты созданы (`pjsip show transports`)
- [ ] Endpoints созданы (`pjsip show endpoints`)
- [ ] Тестовый endpoint зарегистрирован
- [ ] Тестовый звонок работает
- [ ] Django Admin показывает endpoints
- [ ] Python API работает

### Диагностика:

```bash
# Проверка всех компонентов
sudo asterisk -rx "core show version"
sudo asterisk -rx "pjsip show endpoints"
sudo asterisk -rx "database show"
sudo asterisk -rx "manager show connected"

# Проверка через Django
python manage.py setup_asterisk_realtime --validate
```

---

## 📞 Примеры использования

### Пример 1: Click-to-Call из CRM

```python
# views.py
from voip.backends.asteriskbackend import AsteriskRealtimeAPI
from django.conf import settings

def make_call(request, contact_id):
    contact = Contact.objects.get(id=contact_id)
    user_extension = request.user.internal_number.number
    
    config = next(b for b in settings.VOIP if b['PROVIDER'] == 'Asterisk')
    api = AsteriskRealtimeAPI(**config['OPTIONS'])
    
    result = api.originate_call(
        from_endpoint=user_extension,
        to_number=contact.phone,
        callerid=f'"{request.user.get_full_name()}" <{user_extension}>'
    )
    
    return JsonResponse(result)
```

### Пример 2: Автоматическая запись разговоров

```python
# Используйте signals для автоматической записи
from django.db.models.signals import post_save
from voip.models import CallLog

@receiver(post_save, sender=CallLog)
def auto_record_call(sender, instance, created, **kwargs):
    if created and instance.direction == 'inbound':
        config = next(b for b in settings.VOIP if b['PROVIDER'] == 'Asterisk')
        api = AsteriskRealtimeAPI(**config['OPTIONS'])
        
        api.start_recording(
            channel=instance.session_id,
            filename=f'call-{instance.id}',
            format='wav'
        )
```

### Пример 3: Интеграция с очередями

```python
# Добавить агента в очередь при входе в систему
from django.contrib.auth.signals import user_logged_in

@receiver(user_logged_in)
def add_to_queue(sender, user, request, **kwargs):
    if hasattr(user, 'internal_number'):
        config = next(b for b in settings.VOIP if b['PROVIDER'] == 'Asterisk')
        api = AsteriskRealtimeAPI(**config['OPTIONS'])
        
        api.add_queue_member(
            queue='support',
            interface=f'PJSIP/{user.internal_number.number}',
            member_name=user.get_full_name()
        )
```

---

## 📚 Дополнительные ресурсы

- **[ASTERISK_REALTIME_SETUP.md](ASTERISK_REALTIME_SETUP.md)** - Полная документация
- **[ASTERISK_QUICKSTART.md](ASTERISK_QUICKSTART.md)** - Быстрый старт
- **[.env.asterisk.example](.env.asterisk.example)** - Все настройки
- **[voip/README.md](voip/README.md)** - VoIP модуль

---

## 🆘 Помощь

Если что-то не работает:

1. **Проверьте логи Asterisk**: `sudo tail -f /var/log/asterisk/full`
2. **Включите debug**: `sudo asterisk -rx "pjsip set logger on"`
3. **Проверьте подключение к БД**: `sudo asterisk -rx "database show"`
4. **Запустите валидацию**: `python manage.py setup_asterisk_realtime --validate`
5. **Проверьте конфигурацию**: `sudo asterisk -rx "pjsip show settings"`

Удачи! 🚀
