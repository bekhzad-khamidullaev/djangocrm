# Demo data generation

Use the unified generator to create a full set of demo data that showcases CRM, Tasks, Marketing, Massmail, VOIP, Chat, and Analytics dashboards.

Quick start:

- python manage.py setupdata
- python manage.py generate_demo --months 6 --per-month 5 --dashboard --dashboard-user IamSUPER

Flags:

- --months N: Months back for analytics data (default 6)
- --per-month N: Items per month per model for analytics (default 5)
- --dashboard: Create Analytics dashboard for the user
- --dashboard-user USERNAME: Defaults to IamSUPER
- --reset: Remove previously generated demo data safely (only items marked as demo)

What it does:

1) Ensures initial fixtures and a superuser via setupdata
2) Loads base demo records via loaddemo
3) Generates analytics-friendly Requests, Deals, and Payments via loadanalyticsdemo
4) Ensures Marketing demo: Segment, MessageTemplates, Campaign and a stats run
5) Ensures Massmail demo: EmailAccount and two sample EmlMessages
6) Optionally sets up a Dashboard workspace with common plugins

Notes:

- All operations are idempotent; running multiple times won’t duplicate existing demo entries
- Reset removes only obviously demo-tagged data (safe)
- If you need richer CRM demo objects (more companies/leads/deals per stage), we can extend generate_demo further
