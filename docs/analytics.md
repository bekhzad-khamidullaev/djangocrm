# Analytics

Analytics and forecasting are provided by the `analytics` app.

## Features
- BI dashboards and statistics
- Forecasts for leads/deals (Celery driven)
- Daily/Monthly snapshots

## Configuration
- Enable forecasts via env:
  - `ANALYTICS_FORECASTS_ENABLED=True`
  - `ANALYTICS_FORECASTS_CELERY_ENABLED=True`

## Backend Structure
- Models: `analytics/models.py`
- Tasks: `analytics/tasks.py`
- Utils: `analytics/utils/*`

## API
- Dashboard endpoints: `/dashboard/*`
- Analytics endpoints under `/analytics/*` (see OpenAPI).