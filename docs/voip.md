# VoIP Integration

The CRM integrates with multiple telephony backends:
- Asterisk (AMI)
- FreeSWITCH (ESL)
- OnlinePBX/Zadarma via REST APIs

## Configuration
- Configure credentials via environment variables and Django admin
- Default caller ID and provider settings in `.env`

## Features
- Incoming call webhooks and dashboards
- Call logs (`/call-logs`)
- Routing and notifications (see `voip` app)

Refer to `voip/utils/*` and `voip/integrations/*` for implementation details.
