# 🐳 Docker Setup Guide - Django CRM

Complete Docker Compose setup with Redis, Daphne WebSocket server, Celery, and Nginx.

## 📋 Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Git

## 🚀 Quick Start

### 1. Clone and Setup Environment

```bash
# Create .env file from example
cp .env.example .env

# Edit .env with your settings
nano .env
```

### 2. Start Development Environment

```bash
# Using Makefile (recommended)
make dev-up

# Or using docker-compose directly
docker-compose -f docker-compose.dev.yml up -d
```

### 3. Access the Application

- **Django Admin**: http://localhost:8000/admin/
- **WebSocket Test**: http://localhost:8000/common/websocket-test/
- **WebSocket Endpoint**: ws://localhost:8001/ws/chat/test/
- **Redis Commander**: http://localhost:8081/ (development only)

### 4. Create Superuser

```bash
make createsuperuser

# Or manually
docker-compose exec web python manage.py createsuperuser
```

## 📦 What's Included

### Services

1. **web** - Django application (Gunicorn)
   - Port: 8000
   - WSGI server for HTTP requests

2. **daphne** - WebSocket server (Daphne)
   - Port: 8001
   - ASGI server for WebSocket connections

3. **redis** - Redis server
   - Port: 6379
   - Used for Celery and Channels layer

4. **celery_worker** - Celery worker
   - Background task processing

5. **celery_beat** - Celery beat scheduler
   - Periodic task scheduling

6. **nginx** - Nginx reverse proxy
   - Port: 80, 443
   - Routes HTTP and WebSocket traffic

7. **postgres** - PostgreSQL database (production)
   - Port: 5432
   - Can be replaced with MySQL or SQLite

## 🛠️ Makefile Commands

### Development

```bash
make dev-up          # Start development environment
make dev-down        # Stop development environment
make dev-logs        # Show development logs
make dev-shell       # Open Django shell
```

### Production

```bash
make build           # Build Docker images
make up              # Start production environment
make down            # Stop production environment
make restart         # Restart all services
make logs            # Show all logs
make logs-web        # Show web logs
make logs-daphne     # Show Daphne logs
make logs-celery     # Show Celery logs
```

### Database

```bash
make migrate         # Run migrations
make makemigrations  # Create migrations
make createsuperuser # Create superuser
make dbshell         # Open database shell
```

### Utilities

```bash
make shell           # Open Django shell
make bash            # Open bash in web container
make test            # Run tests
make collectstatic   # Collect static files
make clean           # Clean up containers and volumes
make ps              # Show running containers
make redis-cli       # Open Redis CLI
make redis-monitor   # Monitor Redis commands
```

### Initialization

```bash
make init            # Full initialization (setup + build + up + migrate)
```

## 🔧 Configuration Files

### Docker Compose Files

- **docker-compose.yml** - Production configuration
  - Full stack with Nginx, PostgreSQL, Redis
  - Health checks and restart policies
  - Volume management

- **docker-compose.dev.yml** - Development configuration
  - Auto-reload for Django and Daphne
  - SQLite database
  - Redis Commander GUI
  - Debug logging

### Environment Variables

Edit `.env` file to configure:

```bash
# Database
POSTGRES_DB=crm_db
POSTGRES_USER=crm_user
POSTGRES_PASSWORD=crmpass

# Django
DEBUG=True
SECRET_KEY=your-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1

# Redis
REDIS_URL=redis://redis:6379/2
CELERY_BROKER_URL=redis://redis:6379/0

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

## 🏗️ Architecture

```
┌─────────────┐
│   Client    │
│  (Browser)  │
└──────┬──────┘
       │
       │ :80 (HTTP)
       │ :443 (HTTPS)
       │
┌──────▼──────┐
│    Nginx    │  ◄── Reverse Proxy
│  (Alpine)   │
└──────┬──────┘
       │
       ├────────────────┬──────────────┐
       │                │              │
       │ :8000 (HTTP)   │ :8001 (WS)   │
       │                │              │
┌──────▼──────┐  ┌──────▼──────┐      │
│  Gunicorn   │  │   Daphne    │      │
│   (WSGI)    │  │   (ASGI)    │      │
└──────┬──────┘  └──────┬──────┘      │
       │                │              │
       └────────┬───────┘              │
                │                      │
         ┌──────▼──────┐               │
         │   Django    │               │
         │     App     │               │
         └──────┬──────┘               │
                │                      │
       ┌────────┼────────┐             │
       │        │        │             │
┌──────▼──┐ ┌──▼────┐ ┌─▼────────┐    │
│PostgreSQL│ │ Redis │ │  Celery  │    │
│  :5432   │ │ :6379 │ │  Worker  │◄───┘
└──────────┘ └───┬───┘ └──────────┘
                 │
            ┌────▼─────┐
            │  Celery  │
            │   Beat   │
            └──────────┘
```

## 🌐 Network Architecture

### HTTP Flow
```
Browser → Nginx:80 → Gunicorn:8000 → Django
```

### WebSocket Flow
```
Browser → Nginx:80/ws/ → Daphne:8001 → Django Channels → Redis
```

### Celery Flow
```
Django → Redis → Celery Worker → Django ORM
```

## 📊 Container Details

### Resource Allocation

Default configuration:

- **web**: 3 Gunicorn workers, 120s timeout
- **daphne**: Single process (scale horizontally)
- **celery_worker**: 2 concurrent tasks
- **redis**: Append-only file persistence
- **postgres**: Default PostgreSQL settings

### Volume Mounts

- **postgres_data**: PostgreSQL database files
- **redis_data**: Redis persistence
- **static_volume**: Django static files
- **media_volume**: User uploads

## 🔒 Security Considerations

### Development

- Debug mode enabled
- SQLite database
- No SSL/TLS
- All CORS origins allowed

### Production

Update `.env`:

```bash
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
SECRET_KEY=your-very-secret-key-generate-new-one

# Security headers
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
```

Configure SSL in nginx.conf:

```nginx
server {
    listen 443 ssl http2;
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    # ... rest of config
}
```

## 🧪 Testing

### Test WebSocket Connection

```bash
# Using browser console
const ws = new WebSocket('ws://localhost:8001/ws/chat/test/');
ws.onopen = () => console.log('Connected!');
ws.onmessage = (e) => console.log(JSON.parse(e.data));
ws.send(JSON.stringify({message: 'Hello!', username: 'Test'}));
```

### Run Unit Tests

```bash
make test

# Or with coverage
docker-compose exec web python manage.py test --coverage
```

### Load Testing

```bash
# Install k6 (https://k6.io/)
k6 run loadtest-websocket.js
```

## 📝 Common Tasks

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f daphne
docker-compose logs -f celery_worker

# Last 100 lines
docker-compose logs --tail=100 web
```

### Execute Commands in Container

```bash
# Django shell
docker-compose exec web python manage.py shell

# Database shell
docker-compose exec web python manage.py dbshell

# Bash
docker-compose exec web bash

# Redis CLI
docker-compose exec redis redis-cli
```

### Backup Database

```bash
# PostgreSQL
docker-compose exec postgres pg_dump -U crm_user crm_db > backup.sql

# Restore
docker-compose exec -T postgres psql -U crm_user crm_db < backup.sql
```

### Scale Services

```bash
# Scale Daphne (multiple WebSocket servers)
docker-compose up -d --scale daphne=3

# Scale Celery workers
docker-compose up -d --scale celery_worker=4
```

## 🔧 Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs service_name

# Check container status
docker-compose ps

# Rebuild
docker-compose build --no-cache service_name
docker-compose up -d service_name
```

### Database connection issues

```bash
# Check PostgreSQL is running
docker-compose exec postgres pg_isready

# Check connection
docker-compose exec web python manage.py dbshell
```

### Redis connection issues

```bash
# Check Redis is running
docker-compose exec redis redis-cli ping

# Should return: PONG

# Check connections
docker-compose exec redis redis-cli info clients
```

### WebSocket connection fails

```bash
# Check Daphne logs
docker-compose logs -f daphne

# Test Redis channel layer
docker-compose exec web python manage.py shell
>>> from channels.layers import get_channel_layer
>>> channel_layer = get_channel_layer()
>>> await channel_layer.send('test', {'type': 'test'})
```

### Static files not loading

```bash
# Collect static files
docker-compose exec web python manage.py collectstatic --noinput

# Check Nginx config
docker-compose exec nginx nginx -t

# Reload Nginx
docker-compose restart nginx
```

## 🚀 Production Deployment

### 1. Prepare Environment

```bash
# Clone repository
git clone <repo-url>
cd django-crm

# Create .env from example
cp .env.example .env

# Edit production settings
nano .env
```

### 2. Configure SSL Certificates

```bash
# Create SSL directory
mkdir ssl

# Add your certificates
cp /path/to/cert.pem ssl/
cp /path/to/key.pem ssl/

# Or use Let's Encrypt
certbot certonly --standalone -d yourdomain.com
```

### 3. Build and Deploy

```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput
```

### 4. Setup Monitoring

```bash
# Check service health
docker-compose ps

# Monitor logs
docker-compose logs -f

# Setup log rotation
# Add to /etc/logrotate.d/docker-compose
```

### 5. Backup Strategy

```bash
# Database backups (daily cron)
0 2 * * * docker-compose exec postgres pg_dump -U crm_user crm_db | gzip > /backups/crm_$(date +\%Y\%m\%d).sql.gz

# Media files backup
rsync -av /path/to/media/ /backups/media/
```

## 📚 Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Daphne Documentation](https://github.com/django/daphne)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Nginx Configuration Guide](https://nginx.org/en/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [Celery Documentation](https://docs.celeryproject.org/)

## 💡 Tips

1. **Development**: Use `docker-compose.dev.yml` for faster iteration
2. **Logs**: Use `docker-compose logs -f` to monitor real-time
3. **Performance**: Scale Daphne and Celery workers as needed
4. **Security**: Always use environment variables for secrets
5. **Backups**: Automate database and media backups
6. **Monitoring**: Consider adding Prometheus + Grafana
7. **Updates**: Keep Docker images updated regularly

## 🆘 Support

For issues and questions:
- Check logs: `docker-compose logs -f`
- Review documentation: `WEBSOCKET_SETUP.md`
- GitHub Issues: [Project Repository](https://github.com/DjangoCRM/django-crm)
