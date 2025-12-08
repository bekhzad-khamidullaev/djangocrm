#!/bin/bash

# Скрипт для запуска Daphne WebSocket сервера
# Django CRM WebSocket Server Startup Script

echo "Starting Daphne WebSocket Server..."
echo "=================================="

# Проверка установки Redis
if ! command -v redis-cli &> /dev/null
then
    echo "WARNING: Redis не установлен или не найден в PATH"
    echo "Для работы WebSocket с несколькими воркерами нужен Redis"
    echo "Установите Redis: sudo apt-get install redis-server (Ubuntu/Debian)"
    echo "                  brew install redis (macOS)"
    echo ""
fi

# Проверка работы Redis
if command -v redis-cli &> /dev/null
then
    if redis-cli ping > /dev/null 2>&1
    then
        echo "✓ Redis запущен и работает"
    else
        echo "⚠ Redis не запущен. Запустите Redis сервер:"
        echo "  sudo service redis-server start (Linux)"
        echo "  redis-server (manual start)"
        echo ""
    fi
fi

# Проверка установки зависимостей
echo "Проверка зависимостей..."
python -c "import channels" 2>/dev/null || { echo "ERROR: channels не установлен. Выполните: pip install -r requirements.txt"; exit 1; }
python -c "import daphne" 2>/dev/null || { echo "ERROR: daphne не установлен. Выполните: pip install -r requirements.txt"; exit 1; }
echo "✓ Все зависимости установлены"
echo ""

# Запуск Daphne
HOST="${DAPHNE_HOST:-0.0.0.0}"
PORT="${DAPHNE_PORT:-8001}"

echo "Запуск Daphne на $HOST:$PORT"
echo "WebSocket endpoints:"
echo "  - ws://$HOST:$PORT/ws/chat/<room_name>/"
echo "  - ws://$HOST:$PORT/ws/notifications/"
echo ""
echo "Нажмите Ctrl+C для остановки сервера"
echo "=================================="
echo ""

# Запуск с автоматической перезагрузкой при изменении файлов (для разработки)
if [ "$1" == "--reload" ]; then
    daphne -b $HOST -p $PORT --reload webcrm.asgi:application
else
    daphne -b $HOST -p $PORT webcrm.asgi:application
fi
