# Settings and Environment

Most configuration is provided via `.env` (see `.env.example`). Key sections:

## Django
- `DEBUG`, `SECRET_KEY`, `ALLOWED_HOSTS`

## Database (PostgreSQL recommended)
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`

## Redis & Celery
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `CHANNEL_LAYERS_HOST`
- Worker tuning: `CELERY_WORKER_CONCURRENCY`, `CELERY_WORKER_PREFETCH_MULTIPLIER`

## Email
- SMTP settings and `DEFAULT_FROM_EMAIL`

## Security
- `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `X_FRAME_OPTIONS`

## JWT & CORS
- Token lifetimes (`JWT_ACCESS_MINUTES`, `JWT_REFRESH_DAYS`), rotation/blacklist
- `CORS_ALLOW_ALL_ORIGINS` (use with caution)

## VOIP Providers
- Asterisk AMI, FreeSWITCH ESL, OnlinePBX, Zadarma (see voip settings)

See also: `webcrm/settings.py` and `voip/settings.py` for defaults and feature flags.
