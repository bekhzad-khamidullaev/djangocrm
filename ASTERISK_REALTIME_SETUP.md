# Asterisk v21 Realtime Setup

Эта инструкция описывает, как включить собственную телефонию CRM на базе Asterisk **21** с управлением через realtime базу данных. В результате все PJSIP endpoints, AOR, auth, контакты и dialplan будут храниться в PostgreSQL и управляться из Django.

## 1) Предварительные требования
- Asterisk 21 установлен с модулями `res_pjsip`, `res_pjsip_outbound_registration`, `res_odbc`, `res_config_odbc` (или `res_config_pgsql`), `pbx_config`.
- PostgreSQL доступен как из Asterisk, так и из CRM.
- AMI включен и доступен с хоста CRM (для перезагрузок PJSIP и управления звонками).

### Где запустить Asterisk
- **Прод**: отдельный сервер/VM рядом с телефонией (рекомендуется), с доступом к PostgreSQL и AMI.
- **Dev/demo**: можно поднять контейнер Asterisk 21 и подключить его к той же сети, что и CRM. Пример фрагмента `docker-compose` (для локальных тестов, конфиги монтируются из `./asterisk-conf`):
```yaml
  asterisk:
    image: asterisk/asterisk:21
    container_name: asterisk21
    restart: unless-stopped
    environment:
      - ASTERISK_UID=1000
      - ASTERISK_GID=1000
    volumes:
      - ./asterisk-conf/etc:/etc/asterisk
      - ./asterisk-conf/var_lib:/var/lib/asterisk
      - ./asterisk-conf/var_spool:/var/spool/asterisk
      - ./asterisk-conf/var_log:/var/log/asterisk
    ports:
      - "5060:5060/udp"
      - "5060:5060/tcp"
      - "8088:8088"      # HTTP/WS (если нужен)
      - "8089:8089"      # HTTPS/WSS
      - "5038:5038"      # AMI
      - "10000-10100:10000-10100/udp"  # RTP
    networks:
      - crm-network
```
В каталоге `./asterisk-conf/etc` должны лежать подготовленные `pjsip.conf`, `extconfig.conf`, `sorcery.conf`, `res_odbc.conf` и др. из раздела ниже. Для продакшена лучше собирать собственный образ с нужными модулями/драйверами ODBC и не публиковать AMI наружу.

## 2) База данных PostgreSQL
Создайте пользователя и базу, которую будут совместно использовать Asterisk и CRM:

```sql
CREATE ROLE asterisk WITH LOGIN PASSWORD 'strong-pass';
CREATE DATABASE asterisk OWNER asterisk ENCODING 'UTF8';
GRANT ALL PRIVILEGES ON DATABASE asterisk TO asterisk;
```

Загрузите штатную схему Asterisk 21 для realtime (в комплекте с исходниками). Позже миграции Django можно пометить как примененные через `--fake-initial`, если таблицы уже созданы:

```bash
# путь может отличаться, в зависимости от платформы
psql -U asterisk -d asterisk -f /usr/share/asterisk/contrib/realtime/postgresql.sql
```

## 3) Настройка Asterisk на работу с realtime

`/etc/asterisk/res_odbc.conf`
```ini
[asterisk-rt]
enabled => yes
dsn => PostgreSQL-asterisk    ; DSN из odbcinst.ini/odbc.ini
username => asterisk
password => strong-pass
pre-connect => yes
```

`/etc/asterisk/extconfig.conf`
```ini
ps_endpoints   => odbc,asterisk-rt
ps_auths       => odbc,asterisk-rt
ps_aors        => odbc,asterisk-rt
ps_contacts    => odbc,asterisk-rt
ps_transports  => odbc,asterisk-rt
extensions     => odbc,asterisk-rt
```

`/etc/asterisk/sorcery.conf`
```ini
[res_pjsip]
endpoint = realtime,ps_endpoints
auth = realtime,ps_auths
aor = realtime,ps_aors
contact = realtime,ps_contacts
transport = realtime,ps_transports
```

`/etc/asterisk/pjsip.conf`
```ini
[global]
type=global
user_agent=DjangoCRM-Asterisk21
```

Примените конфигурацию:

```bash
asterisk -rx "module reload res_odbc.so"
asterisk -rx "module reload res_pjsip.so"
asterisk -rx "dialplan reload"
```

## 4) Настройка CRM (Django)
Добавьте параметры в `.env` или переменные окружения:

```env
# AMI для управления и перезагрузок
ASTERISK_AMI_HOST=asterisk.local
ASTERISK_AMI_PORT=5038
ASTERISK_AMI_USERNAME=admin
ASTERISK_AMI_SECRET=change-me

# Realtime база Asterisk 21
ASTERISK_DB_ENGINE=django.db.backends.postgresql
ASTERISK_DB_NAME=asterisk
ASTERISK_DB_USER=asterisk
ASTERISK_DB_PASSWORD=strong-pass
ASTERISK_DB_HOST=postgres     # или db/хост Asterisk
ASTERISK_DB_PORT=5432
```

При наличии `ASTERISK_DB_NAME` CRM автоматически добавит соединение `asterisk` и направит модели `ps_endpoints`, `ps_auths`, `ps_aors`, `ps_contacts`, `ps_transports` и `extension` в эту базу.

## 5) Синхронизация и проверка
1. Примените модели PJSIP/Dialplan в базе Asterisk (если таблицы уже есть из штатного SQL — используйте `--fake-initial`):
   ```bash
   python manage.py migrate voip --database=asterisk --fake-initial
   ```
2. Создайте транспорт, учетки и правила из CRM:
   ```bash
   python manage.py setup_asterisk_realtime --create-transports --provision-users --sync-internal-numbers
   ```
3. Убедитесь, что AMI и база работают:
   ```bash
   python manage.py setup_asterisk_realtime --test-connection
   ```
4. После изменений из CRM выполняйте `PJSIPReload`/`DialplanReload` (автоматически дергается через AMI, если указан).

Теперь CRM управляет собственной телефонией на Asterisk 21: добавление пользователей создает endpoints в realtime, а перезагрузки PJSIP происходят без перезапуска Asterisk.
