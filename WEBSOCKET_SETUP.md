# WebSocket Server Setup - Django CRM

## Установка и настройка WebSocket сервера через Daphne

### 📋 Требования

- Python 3.8+
- Redis Server (для production и нескольких воркеров)
- Django 5.2+

### 🚀 Установка

#### 1. Установите зависимости

```bash
pip install -r requirements.txt
```

Это установит:
- `channels>=4.0.0` - Django Channels для WebSocket поддержки
- `daphne>=4.0.0` - ASGI сервер
- `channels-redis>=4.1.0` - Redis backend для Channels

#### 2. Установите и запустите Redis

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo service redis-server start
```

**macOS:**
```bash
brew install redis
brew services start redis
```

**Windows:**
Скачайте Redis с https://redis.io/download или используйте WSL

**Проверка Redis:**
```bash
redis-cli ping
# Должно вернуть: PONG
```

#### 3. Примените миграции (если необходимо)

```bash
python manage.py migrate
```

### 🎯 Запуск сервера

#### Вариант 1: Использование bash скрипта (рекомендуется)

```bash
./start_daphne.sh
```

Для режима разработки с автоматической перезагрузкой:
```bash
./start_daphne.sh --reload
```

#### Вариант 2: Ручной запуск

```bash
# Базовый запуск
daphne -b 0.0.0.0 -p 8001 webcrm.asgi:application

# С автоматической перезагрузкой (для разработки)
daphne -b 0.0.0.0 -p 8001 --reload webcrm.asgi:application

# С указанием количества воркеров
daphne -b 0.0.0.0 -p 8001 --workers 4 webcrm.asgi:application
```

#### Вариант 3: Вместе с Django (для разработки без Redis)

Если у вас нет Redis, можно использовать InMemoryChannelLayer:

1. Откройте `webcrm/settings.py`
2. Раскомментируйте InMemoryChannelLayer в `CHANNEL_LAYERS`
3. Запустите сервер:

```bash
python manage.py runserver 8001
```

⚠️ **Внимание:** InMemoryChannelLayer работает только с одним процессом и не подходит для production.

### 🔗 WebSocket Endpoints

После запуска доступны следующие WebSocket endpoints:

1. **Chat WebSocket** - для чата в реальном времени
   ```
   ws://localhost:8001/ws/chat/<room_name>/
   ```
   
   Пример: `ws://localhost:8001/ws/chat/general/`

2. **Notifications WebSocket** - для уведомлений пользователя
   ```
   ws://localhost:8001/ws/notifications/
   ```
   
   Требует аутентификации пользователя

### 🧪 Тестирование

#### 1. Использование HTML тестового клиента

Откройте в браузере:
```
http://localhost:8000/static/websocket_test.html
```

Или создайте view для отображения `templates/websocket_test.html`

#### 2. Использование браузерной консоли

```javascript
// Подключение к чату
const socket = new WebSocket('ws://localhost:8001/ws/chat/test/');

socket.onopen = function(e) {
    console.log('Connected!');
    socket.send(JSON.stringify({
        'message': 'Hello, WebSocket!',
        'username': 'TestUser'
    }));
};

socket.onmessage = function(event) {
    console.log('Message received:', JSON.parse(event.data));
};

socket.onclose = function(event) {
    console.log('Connection closed');
};
```

#### 3. Использование Python клиента

```python
import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8001/ws/chat/test/"
    async with websockets.connect(uri) as websocket:
        # Отправка сообщения
        await websocket.send(json.dumps({
            'message': 'Hello from Python!',
            'username': 'PythonClient'
        }))
        
        # Получение ответа
        response = await websocket.recv()
        print(f"Received: {response}")

asyncio.run(test_websocket())
```

### 📝 Структура проекта

```
webcrm/
├── asgi.py                 # ASGI конфигурация
├── routing.py              # WebSocket URL маршруты
└── settings.py             # Настройки (CHANNEL_LAYERS, ASGI_APPLICATION)

chat/
└── consumers.py            # WebSocket consumers (ChatConsumer, NotificationConsumer)

templates/
└── websocket_test.html     # HTML тестовый клиент

start_daphne.sh             # Скрипт запуска
```

### ⚙️ Конфигурация

#### Переменные окружения

Вы можете настроить сервер через переменные окружения:

```bash
# Хост и порт Daphne
export DAPHNE_HOST=0.0.0.0
export DAPHNE_PORT=8001

# Redis URL для Channels
export REDIS_URL=redis://localhost:6379/2

# Celery/Redis (уже настроено в settings.py)
export CELERY_BROKER_URL=redis://localhost:6379/0
export CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

#### Настройки в settings.py

```python
# ASGI приложение
ASGI_APPLICATION = 'webcrm.asgi.application'

# Channels Layer (Redis backend)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [os.getenv('REDIS_URL', 'redis://localhost:6379/2')],
        },
    },
}
```

### 🔒 Безопасность

1. **Аутентификация**: WebSocket использует Django authentication middleware
2. **ALLOWED_HOSTS**: Убедитесь, что ваш домен добавлен в `ALLOWED_HOSTS`
3. **CORS**: Для cross-origin WebSocket соединений настройте CORS в settings.py

### 🚀 Production Deployment

#### Systemd Service (Linux)

Создайте файл `/etc/systemd/system/daphne.service`:

```ini
[Unit]
Description=Daphne WebSocket Server
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/django-crm
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/daphne -b 0.0.0.0 -p 8001 webcrm.asgi:application
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Запуск:
```bash
sudo systemctl daemon-reload
sudo systemctl enable daphne
sudo systemctl start daphne
sudo systemctl status daphne
```

#### Nginx Proxy Configuration

```nginx
upstream daphne {
    server 127.0.0.1:8001;
}

server {
    listen 80;
    server_name your-domain.com;

    location /ws/ {
        proxy_pass http://daphne;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }

    # Остальные location для Django...
}
```

#### Docker Compose

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  daphne:
    build: .
    command: daphne -b 0.0.0.0 -p 8001 webcrm.asgi:application
    ports:
      - "8001:8001"
    depends_on:
      - redis
    environment:
      - REDIS_URL=redis://redis:6379/2
```

### 🐛 Troubleshooting

#### Проблема: "Connection refused"
- Убедитесь, что Daphne запущен на правильном порту
- Проверьте firewall правила
- Проверьте, что используете правильный протокол (ws:// не wss://)

#### Проблема: "Redis connection failed"
- Убедитесь, что Redis сервер запущен: `redis-cli ping`
- Проверьте Redis URL в настройках
- Для разработки используйте InMemoryChannelLayer

#### Проблема: "Module not found: channels"
- Установите зависимости: `pip install -r requirements.txt`

#### Проблема: WebSocket закрывается сразу после подключения
- Проверьте логи Daphne
- Убедитесь, что consumer правильно реализован
- Проверьте аутентификацию (для защищенных endpoints)

### 📚 Дополнительные ресурсы

- [Django Channels Documentation](https://channels.readthedocs.io/)
- [Daphne Documentation](https://github.com/django/daphne)
- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)

### 💡 Советы

1. **Разработка**: Используйте `--reload` флаг для автоматической перезагрузки
2. **Production**: Запускайте несколько воркеров Daphne за load balancer
3. **Мониторинг**: Используйте Redis MONITOR для отладки Channels
4. **Логирование**: Настройте logging для channels в Django settings

### 📞 Поддержка

Если возникли вопросы, проверьте:
- Документацию Django Channels
- Issues на GitHub
- Логи сервера: `journalctl -u daphne -f` (systemd)
