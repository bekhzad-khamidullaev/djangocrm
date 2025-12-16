# Production Deployment (Docker Compose + PostgreSQL + GitLab CI)

This page summarizes the production deployment steps. For the full, step-by-step guide, see `PRODUCTION_DEPLOYMENT.md` in the repository root.

## Stack
- Nginx, Daphne (ASGI), Django
- Celery worker + Celery beat
- Redis for broker/results
- PostgreSQL database
- Optional: Asterisk

## Prerequisites
- Linux host with Docker 24+ and Docker Compose v2
- DNS records for your domain
- Open firewall ports 80/443

## Environment
Copy `.env.example` to `.env` and configure:
- `SECRET_KEY`, `ALLOWED_HOSTS`
- PostgreSQL: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
- Redis, Celery URLs
- Security flags for production

## Build & Run (short)
```bash
docker compose -f docker-compose.production.yml build
# Start infra
docker compose -f docker-compose.production.yml up -d postgres redis
# Migrations and static
docker compose -f docker-compose.production.yml run --rm web python manage.py migrate
docker compose -f docker-compose.production.yml run --rm web python manage.py collectstatic --noinput
# Start app
docker compose -f docker-compose.production.yml up -d web daphne celery celery-beat nginx
```

## TLS (Nginx + Certbot)
- Configure `nginx.prod.conf` server_name
- Issue certificates via the `certbot` service
- Enable `SECURE_SSL_REDIRECT=True` after TLS works

## Scaling
- Scale daphne: `docker compose -f docker-compose.production.yml up -d --scale daphne=2`

## CI/CD (GitLab)
- Build image in CI and push to registry
- Deploy via SSH using `docker compose pull` and `up -d`
- Run migrations as a separate step

See full script in `PRODUCTION_DEPLOYMENT.md`.
