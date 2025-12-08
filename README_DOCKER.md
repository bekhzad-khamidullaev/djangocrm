# 🐳 Django CRM - Docker Deployment

Complete Docker setup with Redis, Daphne WebSocket server, Celery workers, and Nginx reverse proxy.

## 📋 Table of Contents

- [Quick Start](#-quick-start)
- [Architecture](#-architecture)
- [Services](#-services)
- [Commands](#-commands)
- [Configuration](#-configuration)
- [Monitoring](#-monitoring)
- [Backup & Restore](#-backup--restore)
- [Troubleshooting](#-troubleshooting)
- [Production Deployment](#-production-deployment)

## 🚀 Quick Start

### Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB disk space

### One-Command Setup

```bash
# Initialize everything
make init
```

This will:
1. ✅ Create `.env` file
2. ✅ Build Docker images
3. ✅ Start all services
4. ✅ Run migrations
5. ✅ Collect static files
6. ✅ Create superuser

### Manual Setup

```bash
# 1. Setup environment
cp .env.example .env
nano .env

# 2. Build and start
docker-compose up -d

# 3. Initialize database
make migrate
make createsuperuser

# 4. Access the app
open http://localhost:8000
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                    ┌────▼────┐
                    │  Nginx  │ :80, :443
                    │ (Proxy) │
                    └────┬────┘
                         │
            ┏━━━━━━━━━━━━┻━━━━━━━━━━━━┓
            ┃                          ┃
      ┌─────▼──────┐           ┌──────▼──────┐
      │  Gunicorn  │           │   Daphne    │
      │    :8000   │           │    :8001    │
      │   (WSGI)   │           │   (ASGI)    │
      └─────┬──────┘           └──────┬──────┘
            │                         │
            └────────┬─────────────┬──┘
                     │             │
              ┌──────▼──────┐      │
              │   Django    │      │
              │     App     │      │
              └──────┬──────┘      │
                     │             │
        ┏━━━━━━━━━━━━┻━━━━━━━━━━━━┻━━━━━━━┓
        ┃            │              │       ┃
   ┌────▼────┐  ┌───▼────┐   ┌─────▼─────┐ │
   │PostgreSQL│  │ Redis  │   │  Celery   │ │
   │  :5432  │  │ :6379  │   │  Workers  │ │
   └─────────┘  └───┬────┘   └───────────┘ │
                    │                       │
               ┌────▼──────┐                │
               │  Celery   │ ◄──────────────┘
               │   Beat    │
               └───────────┘
```

## 📦 Services

### Web (Gunicorn)
- **Port**: 8000
- **Purpose**: HTTP requests, Django admin
- **Workers**: 3 (configurable)
- **Restart**: Always

### Daphne (WebSocket)
- **Port**: 8001
- **Purpose**: WebSocket connections
- **Protocol**: ASGI
- **Scalable**: Yes (horizontal)

### Redis
- **Port**: 6379
- **Purpose**: 
  - Channel layer for WebSockets
  - Celery broker
  - Celery result backend
- **Persistence**: AOF enabled

### PostgreSQL
- **Port**: 5432
- **Database**: crm_db
- **User**: crm_user
- **Backups**: Volume mounted

### Celery Worker
- **Concurrency**: 2 tasks
- **Purpose**: Background jobs
- **Scalable**: Yes

### Celery Beat
- **Purpose**: Periodic tasks
- **Scheduler**: Database-backed

### Nginx
- **Ports**: 80 (HTTP), 443 (HTTPS)
- **Purpose**:
  - Reverse proxy
  - Static files serving
  - WebSocket proxy
  - SSL termination

## 🎯 Commands

### Development

```bash
# Start development environment
make dev-up

# View logs
make dev-logs

# Django shell
make dev-shell

# Stop
make dev-down
```

### Production

```bash
# Build images
make build

# Start services
make up

# View logs (all)
make logs

# View logs (specific service)
make logs-web
make logs-daphne
make logs-celery

# Stop services
make down

# Restart services
make restart
```

### Database

```bash
# Run migrations
make migrate

# Create migrations
make makemigrations

# Create superuser
make createsuperuser

# Database shell
make dbshell
```

### Utilities

```bash
# Django shell
make shell

# Bash in container
make bash

# Run tests
make test

# Collect static files
make collectstatic

# Container status
make ps

# Redis CLI
make redis-cli

# Redis monitor
make redis-monitor
```

### Maintenance

```bash
# Health check
./scripts/health-check.sh

# Backup
./scripts/backup.sh

# Restore
./scripts/restore.sh

# Clean up
make clean

# Clean all (including images)
make clean-all
```

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# Django
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
POSTGRES_DB=crm_db
POSTGRES_USER=crm_user
POSTGRES_PASSWORD=strong-password-here
DATABASE_URL=postgresql://crm_user:password@postgres:5432/crm_db

# Redis
REDIS_URL=redis://redis:6379/2
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_PORT=587
EMAIL_USE_TLS=True

# Security (Production)
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
```

### Docker Compose Files

- `docker-compose.yml` - Production setup
- `docker-compose.dev.yml` - Development setup with auto-reload
- `docker-compose.prod.yml` - Production with multiple Daphne instances

### Scaling Services

```bash
# Scale Daphne WebSocket servers
docker-compose up -d --scale daphne=3

# Scale Celery workers
docker-compose up -d --scale celery_worker=4
```

## 📊 Monitoring

### Container Status

```bash
# All containers
docker-compose ps

# Resource usage
docker stats

# Health check
./scripts/health-check.sh
```

### Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f daphne

# Last 100 lines
docker-compose logs --tail=100 celery_worker
```

### Redis Monitoring

```bash
# Redis GUI (development)
open http://localhost:8081

# Redis CLI
docker-compose exec redis redis-cli

# Monitor commands
docker-compose exec redis redis-cli monitor

# Check connections
docker-compose exec redis redis-cli client list
```

### Database Monitoring

```bash
# PostgreSQL info
docker-compose exec postgres psql -U crm_user -d crm_db -c "\l"

# Active connections
docker-compose exec postgres psql -U crm_user -d crm_db -c "SELECT * FROM pg_stat_activity;"

# Database size
docker-compose exec postgres psql -U crm_user -d crm_db -c "SELECT pg_size_pretty(pg_database_size('crm_db'));"
```

## 💾 Backup & Restore

### Automatic Backup

```bash
# Run backup script
./scripts/backup.sh

# Setup cron for daily backups
0 2 * * * /path/to/django-crm/scripts/backup.sh
```

### Manual Backup

```bash
# PostgreSQL
docker-compose exec postgres pg_dump -U crm_user crm_db | gzip > backup.sql.gz

# Redis
docker-compose exec redis redis-cli SAVE
docker cp crm_redis:/data/dump.rdb redis_backup.rdb

# Media files
tar -czf media_backup.tar.gz ./media
```

### Restore

```bash
# Using restore script
./scripts/restore.sh

# Manual PostgreSQL restore
gunzip -c backup.sql.gz | docker-compose exec -T postgres psql -U crm_user crm_db

# Manual Redis restore
docker cp redis_backup.rdb crm_redis:/data/dump.rdb
docker-compose restart redis

# Media files
tar -xzf media_backup.tar.gz
```

## 🔧 Troubleshooting

### Service Won't Start

```bash
# Check logs
docker-compose logs service_name

# Rebuild container
docker-compose build --no-cache service_name
docker-compose up -d service_name

# Check configuration
docker-compose config
```

### Database Connection Error

```bash
# Check PostgreSQL
docker-compose exec postgres pg_isready

# Check credentials
echo $DATABASE_URL

# Test connection
docker-compose exec web python manage.py dbshell
```

### Redis Connection Error

```bash
# Check Redis
docker-compose exec redis redis-cli ping

# Check configuration
docker-compose exec web python -c "import redis; r=redis.from_url('redis://redis:6379/2'); print(r.ping())"
```

### WebSocket Not Working

```bash
# Check Daphne logs
docker-compose logs -f daphne

# Test WebSocket
wscat -c ws://localhost:8001/ws/chat/test/

# Check Nginx proxy
curl -I http://localhost:8001
```

### Static Files Not Loading

```bash
# Collect static files
make collectstatic

# Check Nginx configuration
docker-compose exec nginx nginx -t

# Restart Nginx
docker-compose restart nginx
```

### High Memory Usage

```bash
# Check memory usage
docker stats

# Reduce Gunicorn workers (in docker-compose.yml)
command: gunicorn --workers 2 ...

# Reduce Celery concurrency
command: celery -A webcrm worker --concurrency=1 ...
```

## 🚀 Production Deployment

### 1. Server Setup

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Clone and Configure

```bash
# Clone repository
git clone <your-repo-url>
cd django-crm

# Setup environment
cp .env.example .env
nano .env  # Edit production settings
```

### 3. SSL Certificates

```bash
# Option 1: Let's Encrypt
certbot certonly --standalone -d yourdomain.com
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/cert.pem
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/key.pem

# Option 2: Self-signed (testing only)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/key.pem -out ssl/cert.pem
```

### 4. Deploy

```bash
# Build and start
docker-compose -f docker-compose.prod.yml up -d

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput
```

### 5. Setup Monitoring

```bash
# Install monitoring tools
docker run -d --name prometheus ...
docker run -d --name grafana ...

# Setup log aggregation
docker run -d --name elk-stack ...
```

### 6. Backup Strategy

```bash
# Setup automated backups
crontab -e

# Add daily backup at 2 AM
0 2 * * * /path/to/django-crm/scripts/backup.sh

# Add weekly offsite backup
0 3 * * 0 rsync -av /path/to/backups/ remote:/backups/
```

## 🔒 Security Checklist

- [ ] Change all default passwords
- [ ] Set strong `SECRET_KEY`
- [ ] Configure SSL/TLS certificates
- [ ] Set `DEBUG=False` in production
- [ ] Restrict `ALLOWED_HOSTS`
- [ ] Enable firewall (only ports 80, 443, 22)
- [ ] Setup fail2ban for SSH
- [ ] Regular security updates
- [ ] Database password encryption
- [ ] Secure Redis with password
- [ ] Enable Docker security scanning
- [ ] Setup log monitoring
- [ ] Regular backups

## 📚 Additional Documentation

- **WebSocket Setup**: `WEBSOCKET_SETUP.md`
- **Quick Start**: `QUICKSTART_DOCKER.md`
- **Full Docker Guide**: `DOCKER_SETUP.md`
- **Makefile Commands**: `make help`

## 🆘 Support

- **Documentation**: [Django CRM Docs](https://djangocrm.github.io/info/)
- **GitHub Issues**: [Report bugs](https://github.com/DjangoCRM/django-crm/issues)
- **Docker Hub**: [Docker images](https://hub.docker.com/r/djangocrm/crm)

## 📝 License

MIT License - see LICENSE file

---

**Built with ❤️ using Django, Daphne, Redis, and Docker**
