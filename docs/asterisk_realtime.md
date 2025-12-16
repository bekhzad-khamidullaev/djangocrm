# Asterisk Realtime

Optional integration with Asterisk for telephony.

## Modes
- AMI for control and events
- Realtime for SIP peers/users (if enabled)

## Configuration
- Environment variables for AMI (host, port, user, secret)
- See `voip/integrations/asterisk*` and `voip/utils/asterisk_realtime.py`

## Compose
- `docker-compose.production.yml` includes an `asterisk` service. Mount configs from `asterisk/config/`.

## Notes
- Secure AMI with strong credentials and limited network access
- Verify NAT/RTP settings in `pjsip.conf`