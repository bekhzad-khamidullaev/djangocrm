# Production Deployment Guide (Docker Compose + PostgreSQL + GitLab CI)

This guide describes a secure, repeatable production setup for the Django CRM using Docker Compose and PostgreSQL, with GitLab CI for build, test, and deploy.

## 1. Overview
- Orchestrator: Docker Compose (see docker-compose.production.yml)
- Web server: Nginx (reverse proxy, static/media)
- App server: Daphne (ASGI) + Django
- Background: Celery worker + Celery beat
- Cache/Queue: Redis
- Database: PostgreSQL
- TLS: Nginx + Certbot (optional)
- Telephony (optional): Asterisk container

## 2. Prerequisites
- Host: Ubuntu 22.04 LTS (recommended) or any Linux with Docker 24.x+ and Docker Compose v2
- DNS: A/AAAA records for your domain pointing to the server IP
- Firewall: Allow 80/tcp and 443/tcp
- GitLab Container Registry or another OCI registry for images

## 3. Environment and Secrets
- Copy .env.example to .env and update values. Key sections:
  - SECRET_KEY, ALLOWED_HOSTS
  - PostgreSQL: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST, POSTGRES_PORT
  - Redis passwords, Celery URLs
  - Email settings (SMTP) if needed
  - Security flags: SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE

Store .env outside of version control. In CI, use GitLab CI variables.

## 4. Persistent Volumes
docker-compose.production.yml defines volumes:
- postgres_data: PostgreSQL data
- asterisk_recordings (optional)
- static/media directories are served by Nginx (mounts configured in compose)

Back up these volumes regularly (see Backups section).

## 5. Build and Images
Two options:
1) Build on the server (simpler):
   - docker compose -f docker-compose.production.yml build
2) Build in CI and push to a registry (recommended):
   - CI builds and pushes app image (see GitLab CI section)
   - Server pulls and recreates services

## 6. Database Setup
Initial deployment:
- Ensure PostgreSQL is running (container postgres)
- Apply migrations: docker compose -f docker-compose.production.yml run --rm web python manage.py migrate
- Create superuser: docker compose -f docker-compose.production.yml run --rm web python manage.py createsuperuser
- Collect static: docker compose -f docker-compose.production.yml run --rm web python manage.py collectstatic --noinput

## 7. Starting Services
- docker compose -f docker-compose.production.yml up -d postgres redis
- docker compose -f docker-compose.production.yml up -d web daphne celery celery-beat nginx
- Optional: up asterisk and certbot if required

Verify health:
- docker compose ps
- docker compose logs -f web daphne nginx

## 8. Nginx and TLS
- The compose includes nginx and optional certbot. For first-time issuance:
  - Set correct server_name in nginx.prod.conf
  - Expose 80/443 on the host
  - Run certbot service or issue certificates manually, then reload nginx
- Ensure SECURE_SSL_REDIRECT=True in .env after TLS works

## 9. Scaling
- Horizontal app scaling via multiple daphne instances is supported (see docker-compose.prod.yml for example). In production.yml, adjust replicas by running multiple daphne services or scale:
  - docker compose -f docker-compose.production.yml up -d --scale daphne=2
- Ensure nginx upstream matches the scaled services (template can use service DNS names)

## 10. Celery and Scheduling
- Celery worker handles background tasks
- Celery beat schedules periodic jobs (e.g., analytics forecasts)
- Configure concurrency via CELERY_WORKER_CONCURRENCY in .env

## 11. Logs and Monitoring
- Use docker compose logs -f SERVICE
- Consider shipping logs to ELK/Datadog/Vector
- Health checks: add Docker healthcheck or external probes
- Flower can be enabled for Celery monitoring (if included)

## 12. Backups and Restore
- Database backup:
  - docker compose -f docker-compose.production.yml exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup_$(date +%F).sql
- Database restore:
  - docker compose -f docker-compose.production.yml exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" < backup.sql
- Volume backup: use docker run --rm -v volume:/data -v "$PWD":/backup alpine tar czf /backup/volume_$(date +%F).tgz -C /data .

Automate backups via cron or GitLab scheduled pipelines.

## 13. Zero-downtime Deployment (basic)
- Build and push image (CI)
- On server:
  - docker compose -f docker-compose.production.yml pull web daphne
  - docker compose -f docker-compose.production.yml up -d web daphne
- Run migrations in a controlled step: run migrate before switching traffic if there are breaking schema changes

## 14. Security Hardening
- Rotate SECRET_KEY and credentials regularly
- Enforce HTTPS (HSTS) once TLS is stable
- Limit admin access by IP or VPN
- Set proper ALLOWED_HOSTS
- Keep images updated; run docker image prune regularly
- Regularly update dependencies (pip, OS packages)

## 15. Upgrades and Rollbacks
- Use versioned images (e.g., registry/app:1.2.3)
- For rollback: docker compose -f docker-compose.production.yml up -d web@sha256:<digest> daphne@sha256:<digest>
- Keep DB migrations backward-compatible when possible

## 16. GitLab CI Example
Include the following .gitlab-ci.yml (simplified) to build and deploy:

```yaml
stages: [test, build, deploy]

variables:
  DOCKER_DRIVER: overlay2
  APP_IMAGE: "$CI_REGISTRY_IMAGE/app:$CI_COMMIT_SHA"

services:
  - docker:dind

before_script:
  - echo "$CI_REGISTRY_PASSWORD" | docker login -u "$CI_REGISTRY_USER" --password-stdin "$CI_REGISTRY"

pytest:
  stage: test
  image: python:3.11-slim
  script:
    - pip install -r requirements.txt
    - pytest -q

build:
  stage: build
  image: docker:24
  script:
    - docker build -t "$APP_IMAGE" .
    - docker push "$APP_IMAGE"
  only:
    - main

.deploy_template: &deploy_script
  - ssh -o StrictHostKeyChecking=no $SSH_USER@$SSH_HOST "\
      export APP_IMAGE=$APP_IMAGE; \
      cd $DEPLOY_DIR; \
      sed -i 's|image: .*|image: '"$APP_IMAGE"'|' docker-compose.production.yml; \
      docker compose -f docker-compose.production.yml pull web daphne; \
      docker compose -f docker-compose.production.yml up -d web daphne celery celery-beat nginx; \
      docker compose -f docker-compose.production.yml run --rm web python manage.py migrate; \
    "

deploy:
  stage: deploy
  image: alpine:3.19
  before_script:
    - apk add --no-cache openssh-client
  script:
    - *deploy_script
  environment:
    name: production
    url: https://yourdomain.com
  only:
    - tags
```

Notes:
- Use SSH deploy keys and a non-root user on the server
- Consider templating compose with envsubst or Helmfile-in-Compose for multi-env

## 17. Troubleshooting
- 502/504 from Nginx: check daphne service health and upstream config
- Static files not served: ensure collectstatic ran and volumes mounted in nginx
- WebSockets not working: confirm Nginx config supports upgrade headers and routes to daphne
- Celery tasks stuck: verify Redis connectivity and CELERY_BROKER_URL

## 18. Optional: Asterisk
- docker-compose.production.yml includes an asterisk service. Enable only if you need on-box telephony. Otherwise use external PBX providers via voip app settings.

--
This guide is tailored to this repository's compose files and .env structure.
