# Django CRM Documentation

Welcome to the official documentation for the Django-based CRM.

This site covers:
- Production deployment with Docker Compose and PostgreSQL
- Frontend development with Next.js + Ant Design, fully covering the CRM API
- API overview and authentication
- Application settings and environment
- Telephony (VoIP) integration

Quick links:
- Deployment → [Production Guide](deployment.md)
- Frontend → [Next.js + AntD Guide](frontend.md)
- API → [Overview and Auth](api.md)
- Settings → [Environment Variables](settings.md)
- VoIP → [Telephony Integration](voip.md)

## Быстрый старт

Предпосылки:
- Python 3.10+
- Docker и Docker Compose (рекомендуется для prod/dev)
- Make (опционально)

1) Клонировать репозиторий и подготовить окружение

```bash
cp .env.example .env
# при необходимости отредактируйте переменные окружения
```

2) Инициализировать базу данных и создать суперпользователя (локально)

```bash
python -m venv venv && source venv/bin/activate  # Windows: venv\\Scripts\\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py loaddata common/fixtures/sites.json common/fixtures/groups.json common/fixtures/department.json
python manage.py createsuperuser
```

3) Запуск в DEV через Docker Compose

```bash
docker compose up -d --build
# Бэкенд будет доступен на http://localhost:8000
```

Либо без Docker (локально):

```bash
python manage.py runserver 0.0.0.0:8000
```

4) Документация локально (MkDocs)

```bash
pip install -r docs/site/requirements.txt
mkdocs serve  # откроется на http://127.0.0.1:8000
```

Read the Docs:
- Конфигурация: `.readthedocs.yaml`
- Тема/навигация: `mkdocs.yml`
- Контент: `docs/`

5) Генерация фронтенд‑клиента из OpenAPI (см. AGENTS.md)

```bash
# пример с openapi-typescript-codegen
npx openapi-typescript-codegen \
  --input http://localhost:8000/openapi-schema.yml \
  --output src/shared/api \
  --client axios
```

## Repository Layout
- Django backend (this repo)
- OpenAPI schemas: `openapi-schema.yml`, `openapi-schema-generated.yml`
- Compose files: `docker-compose.production.yml`, `docker-compose.prod.yml`

## Getting Help
- Issues: your Git hosting issues
- Community: TBD
