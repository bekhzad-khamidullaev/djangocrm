# API Overview

The CRM exposes a comprehensive REST API documented via OpenAPI.

- Legacy schema: `openapi-schema.yml`
- Generated v3 skeleton: `openapi-schema-generated.yml`

## Authentication
- JWT endpoints: `/token/`, `/token/refresh/`, `/token/verify/`
- Use `Authorization: Bearer <access_token>`

## Core Resources (examples)
- Companies: `/companies`, `/companies/{id}`
- Contacts: `/contacts`, `/contacts/{id}`
- Deals & Stages: `/deals`, `/stages`
- Leads: `/leads`, actions: `/leads/{id}/assign`, `/convert`, `/disqualify`, bulk: `/leads/bulk_tag`
- Tasks & Projects: `/tasks`, `/projects`, stages references
- Marketing: `/marketing/*`
- Massmail: `/massmail/*`
- Tags: `/crm-tags`, `/task-tags`
- Dashboard: `/dashboard/*`
- VoIP: `/voip/*`, Call logs: `/call-logs`

Use the schema to generate fully-typed clients (see Frontend page).
