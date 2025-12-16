#!/bin/bash
set -e

echo "🚀 Starting Django CRM entrypoint..."

# Wait for PostgreSQL
if [ "$DATABASE_ENGINE" = "django.db.backends.postgresql" ]; then
    echo "⏳ Waiting for PostgreSQL..."
    while ! nc -z ${POSTGRES_HOST:-postgres} ${POSTGRES_PORT:-5432}; do
        sleep 0.1
    done
    echo "✅ PostgreSQL started"
fi

# Wait for Redis
echo "⏳ Waiting for Redis..."
while ! nc -z ${REDIS_HOST:-redis} ${REDIS_PORT:-6379}; do
    sleep 0.1
done
echo "✅ Redis started"

# Run migrations
echo "🔄 Running database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "📦 Collecting static files..."
python manage.py collectstatic --noinput --clear

# Create superuser if doesn't exist
echo "👤 Checking for superuser..."
python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin'
    )
    print("✅ Superuser created: admin/admin")
else:
    print("✅ Superuser already exists")
END

echo "✅ Entrypoint complete. Starting application..."

# Execute the main command
exec "$@"
