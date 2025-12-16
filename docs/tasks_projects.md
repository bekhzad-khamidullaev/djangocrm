# Tasks & Projects

Task and project management live in the `tasks` app.

## Entities
- Tasks: `/tasks`, details `/tasks/{id}`
- Projects: `/projects`, details `/projects/{id}`
- Stages: `/task-stages`, `/project-stages`
- Tags: `/task-tags`

## Features
- Task lifecycle (create, assign, complete)
- Project stages and progress
- Filters, tags, and bulk operations

## Backend Structure
- Models in `tasks/models/*`
- Admin and filters in `tasks/site/*` and `tasks/utils/admfilters.py`
- Views under `tasks/views/*`

## API Usage
- Use DRF pagination and ordering
- For bulk tagging projects: `/projects/bulk_tag/`