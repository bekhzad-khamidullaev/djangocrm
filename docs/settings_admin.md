# Settings (Admin)

Administrative configuration exposed via the `settings` app and Django admin.

## Models
- Global settings, social integrations, reminders (see `settings/models.py`)

## Fixtures
- Default settings in `settings/fixtures/*`

## Admin UI
- Available under Django admin → Settings

## API
- `api/settings_*` endpoints for reading/updating settings (see source under `api/settings_*`)

## Security
- Limit access to staff/superusers
- Use environment variables for secrets; avoid storing sensitive values in DB
