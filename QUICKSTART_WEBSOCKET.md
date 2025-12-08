# 🚀 Быстрый запуск WebSocket сервера

## За 5 минут

### 1. Установите зависимости
```bash
pip install -r requirements.txt
```

### 2. Запустите Redis (если не запущен)
```bash
# Linux/Ubuntu
sudo service redis-server start

# macOS
brew services start redis

# Или просто
redis-server
```

### 3. Запустите Daphne WebSocket сервер
```bash
./start_daphne.sh
```

Или вручную:
```bash
daphne -b 0.0.0.0 -p 8001 webcrm.asgi:application
```

### 4. Протестируйте

Откройте в браузере:
```
http://localhost:8000/common/websocket-test/
```

Или используйте консоль браузера:
```javascript
const ws = new WebSocket('ws://localhost:8001/ws/chat/test/');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.onopen = () => ws.send(JSON.stringify({
    message: 'Hello!', 
    username: 'Test'
}));
```

## 📍 Доступные endpoints

- **Chat**: `ws://localhost:8001/ws/chat/<room_name>/`
- **Notifications**: `ws://localhost:8001/ws/notifications/`

## ⚡ Без Redis (только для разработки)

Если нет Redis, отредактируйте `webcrm/settings.py`:

```python
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }
}
```

Затем запустите Django:
```bash
python manage.py runserver 8001
```

## 📚 Полная документация

Смотрите `WEBSOCKET_SETUP.md` для подробной информации.

## 🔧 Проблемы?

**WebSocket не подключается?**
- Проверьте, что Daphne запущен: `curl http://localhost:8001`
- Проверьте Redis: `redis-cli ping`
- Смотрите логи Daphne

**Нужна помощь?**
- Читайте `WEBSOCKET_SETUP.md`
- Проверяйте логи: `journalctl -u daphne -f`
