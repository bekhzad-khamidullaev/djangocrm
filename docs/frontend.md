# Frontend Development (Next.js + Ant Design)

This guide describes building a separate frontend repository using Next.js (App Router) and Ant Design to fully cover the Django CRM API.

Key points (see `AGENTS.md` in repo root for full detail):
- TypeScript, AntD v5, React Query, Axios, Zod, i18next
- OpenAPI code generation for typed API client
- JWT auth: `/token/`, `/token/refresh/`, `/users/me/`
- Standard pages: Companies, Contacts, Deals, Leads, Tasks, Projects, Marketing, Massmail, Analytics, Settings, VoIP

## Project Structure (separate repo)
```
src/
  app/ (...routes...)
  shared/ (ui, config, lib, hooks)
  entities/
  features/
  widgets/
  processes/
public/
```

## API Client
Generate from the backend schema:
```bash
npx openapi-typescript-codegen \
  --input https://api.yourdomain.com/openapi-schema.yml \
  --output src/shared/api \
  --client axios
```
Wrap endpoints into React Query hooks for caching, pagination and mutations.

## Auth
- Refresh token in httpOnly cookie via backend proxy
- Access token in memory or non-HTTP-only cookie for SSR
- Interceptors for 401/403/5xx

## Tables & Forms
- Server-side pagination and filters according to DRF
- AntD Form + Zod for validation; show DRF field errors

## Testing & CI
- Jest + RTL for unit, Playwright for e2e
- CI: lint → typecheck → unit → build → e2e
