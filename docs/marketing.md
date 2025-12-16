# Marketing

Marketing automation and campaigns are provided by the `marketing` app.

## Core Entities
- Campaigns: `/marketing/campaigns`
- Templates: `/marketing/templates`
- Segments: `/marketing/segments`

## Features
- Audience segmentation (rules-based)
- Scheduled or ad-hoc sends
- Renderers and senders pipeline

## Backend Structure
- Models: `marketing/models/*`
- Services: `marketing/services/*` (renderer, sender, scheduler, segmenter)
- Views/URLs: `marketing/views.py`, `marketing/urls.py`

## Tips
- Store templates with variables and test via preview endpoints
- Track delivery metrics and bounces
