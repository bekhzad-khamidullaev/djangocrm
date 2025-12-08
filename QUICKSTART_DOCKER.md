# 🚀 Docker Quick Start - Django CRM

## За 5 минут

### 1. Подготовка

```bash
# Убедитесь, что Docker установлен
docker --version
docker-compose --version

# Клонируйте репозиторий (если еще не сделано)
# git clone <repo-url>
# cd django-crm

# Создайте .env файл
cp .env.example .env
```

### 2. Запуск разработки

```bash
# Запустите все сервисы
make dev-up

# Или без Makefile
docker-compose -f docker-compose.dev.yml up -d
```

### 3. Создайте суперпользователя

```bash
make createsuperuser

# Или
docker-compose exec web python manage.py createsuperuser
```

### 4. Откройте браузер

- **Django Admin**: http://localhost:8000/admin/
- **WebSocket Test**: http://localhost:8000/common/websocket-test/
- **Redis Commander**: http://localhost:8081/

## ✅ Готово!

Ваш CRM запущен и готов к работе.

---

## 📦 Что запущено?

```bash
# Проверьте статус
docker-compose ps

# Или
make ps
```

Вы увидите:
- ✅ **web** - Django сервер (порт 8000)
- ✅ **daphne** - WebSocket сервер (порт 8001)
- ✅ **redis** - Redis для Celery и WebSocket
- ✅ **celery_worker** - Обработка фоновых задач
- ✅ **redis_commander** - GUI для Redis (dev)

---

## 🔧 Основные команды

```bash
# Просмотр логов
make logs              # Все логи
make logs-web          # Только Django
make logs-daphne       # Только WebSocket

# Остановка
make dev-down

# Перезапуск
docker-compose restart

# Выполнение команд Django
make shell             # Django shell
make bash              # Bash в контейнере
make migrate           # Миграции
make test              # Тесты
```

---

## 🧪 Тест WebSocket

### Вариант 1: Браузер
Откройте: http://localhost:8000/common/websocket-test/

### Вариант 2: Консоль браузера
```javascript
const ws = new WebSocket('ws://localhost:8001/ws/chat/test/');
ws.onopen = () => {
    console.log('Подключено!');
    ws.send(JSON.stringify({
        message: 'Привет!',
        username: 'Test'
    }));
};
ws.onmessage = (e) => console.log('Получено:', JSON.parse(e.data));
```

---

## 🌐 Production запуск

```bash
# 1. Настройте .env для production
nano .env

# 2. Запустите production stack
docker-compose up -d

# 3. Выполните миграции
make migrate

# 4. Создайте суперпользователя
make createsuperuser

# 5. Соберите статику
make collectstatic
```

---

## 🔥 Быстрые решения проблем

### Контейнеры не запускаются?
```bash
# Пересоберите
docker-compose build --no-cache
docker-compose up -d
```

### База данных не подключается?
```bash
# Проверьте PostgreSQL
docker-compose exec postgres pg_isready

# Или используйте SQLite (отредактируйте .env)
DATABASE_URL=sqlite:///crm_db.sqlite3
```

### Redis не работает?
```bash
# Проверьте Redis
docker-compose exec redis redis-cli ping
# Должно вернуть: PONG
```

### WebSocket не подключается?
```bash
# Проверьте Daphne логи
docker-compose logs -f daphne

# Проверьте, что порт 8001 открыт
curl http://localhost:8001
```

---

## 📚 Дополнительная информация

- **Полная документация**: `DOCKER_SETUP.md`
- **WebSocket setup**: `WEBSOCKET_SETUP.md`
- **Makefile команды**: `make help`

---

## 🆘 Помощь

```bash
# Все доступные команды
make help

# Логи конкретного сервиса
docker-compose logs -f <service-name>

# Статус всех контейнеров
docker-compose ps

# Полная очистка
make clean
```

---

## 🎉 Готово к работе!

Теперь вы можете:
- ✅ Разрабатывать с автоматической перезагрузкой
- ✅ Тестировать WebSocket в реальном времени
- ✅ Запускать Celery задачи
- ✅ Мониторить Redis через GUI
- ✅ Деплоить в production с Nginx

**Удачной разработки! 🚀**
