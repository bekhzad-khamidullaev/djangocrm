#!/bin/bash
set -e

echo "==================================="
echo "Django CRM Docker Entrypoint"
echo "==================================="

# Wait for database to be ready
if [ -n "$DATABASE_URL" ]; then
    echo "Waiting for database..."
    
    # Extract database type from DATABASE_URL
    if [[ $DATABASE_URL == postgres* ]]; then
        echo "PostgreSQL database detected"
        until PGPASSWORD=$POSTGRES_PASSWORD psql -h "postgres" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q' 2>/dev/null; do
            echo "PostgreSQL is unavailable - sleeping"
            sleep 1
        done
        echo "PostgreSQL is up!"
    elif [[ $DATABASE_URL == mysql* ]]; then
        echo "MySQL database detected"
        until mysqladmin ping -h "mysql" --silent 2>/dev/null; do
            echo "MySQL is unavailable - sleeping"
            sleep 1
        done
        echo "MySQL is up!"
    else
        echo "SQLite or other database - no wait required"
    fi
fi

# Wait for Redis to be ready
if [ -n "$REDIS_URL" ]; then
    echo "Waiting for Redis..."
    REDIS_HOST=$(echo $REDIS_URL | sed -E 's#redis://([^:/]+).*#\1#')
    until redis-cli -h "$REDIS_HOST" ping 2>/dev/null; do
        echo "Redis is unavailable - sleeping"
        sleep 1
    done
    echo "Redis is up!"
fi

# Run migrations
echo "Running database migrations..."
python manage.py migrate --noinput

# Collect static files
if [ "$SKIP_COLLECTSTATIC" != "true" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput --clear
fi

# Create superuser if it doesn't exist
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Creating superuser..."
    python manage.py shell << END
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser(
        username='$DJANGO_SUPERUSER_USERNAME',
        email='${DJANGO_SUPERUSER_EMAIL:-admin@example.com}',
        password='$DJANGO_SUPERUSER_PASSWORD'
    )
    print('Superuser created!')
else:
    print('Superuser already exists.')
END
fi

echo "==================================="
echo "Starting application..."
echo "==================================="

# Execute the main command
exec "$@"
