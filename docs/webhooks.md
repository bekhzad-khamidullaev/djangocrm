# Webhooks

The CRM exposes and consumes webhooks, especially for VoIP and email integrations.

## Incoming Webhooks
- VoIP providers (OnlinePBX, Zadarma, Asterisk): see `voip/views/*` and `voip/utils/webhook_*`
- Validate signatures and IP filtering when available

## Outgoing Webhooks
- Configure via admin/settings or code hooks

## Security
- Always validate HMAC/signatures
- Use HTTPS and rotate secrets

## Debugging
- Log request/response bodies with care (mask PII)
- Use retry/backoff for transient failures
