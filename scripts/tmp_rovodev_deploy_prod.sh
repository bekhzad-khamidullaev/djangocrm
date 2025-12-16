#!/usr/bin/env bash
set -euo pipefail

COMPOSE="docker compose -f docker-compose.production.yml"
DOMAIN_CRM="crm.windevs.uz"
DOMAIN_PBX="pbx.windevs.uz"
EMAIL_ACME="admin@windevs.uz"

step() { echo -e "\n==== $* ===="; }

# Pre-flight
step "Pre-flight checks"
command -v docker >/dev/null || { echo "Docker is required"; exit 1; }
$COMPOSE version >/dev/null || { echo "Docker Compose v2 is required"; exit 1; }

# Show key environment values
step "Environment summary"
export $(grep -E '^(POSTGRES_PASSWORD|REDIS_PASSWORD|ASTERISK_DB_PASSWORD|ASTERISK_AMI_SECRET|ALLOWED_HOSTS|ASTERISK_EXTERNAL_IP|JSSIP_WS_URI)=' .env | xargs) || true
echo "ALLOWED_HOSTS=$ALLOWED_HOSTS"
echo "ASTERISK_EXTERNAL_IP=${ASTERISK_EXTERNAL_IP:-unset}";

# Build images
step "Build images (web, daphne, asterisk)"
$COMPOSE build web daphne asterisk

# Start DB/cache
step "Start postgres and redis"
$COMPOSE up -d postgres redis

# Wait for health
step "Waiting for postgres/redis health"
sleep 8
$COMPOSE ps

# Run Django migrations and collectstatic
step "Apply Django migrations"
$COMPOSE run --rm web python manage.py migrate

step "Create superuser (press Ctrl+C to skip if already created)"
$COMPOSE run --rm web python manage.py createsuperuser || true

step "Collect static"
$COMPOSE run --rm web python manage.py collectstatic --noinput

# Start core services
step "Start application services (asterisk, web, daphne, celery, celery-beat, nginx)"
$COMPOSE up -d asterisk web daphne celery celery-beat nginx

# First issue TLS certificates if missing
if [ ! -d certbot/conf/live/${DOMAIN_CRM} ] || [ ! -d certbot/conf/live/${DOMAIN_PBX} ]; then
  step "Issuing initial Let's Encrypt certificates for ${DOMAIN_CRM} and ${DOMAIN_PBX}"
  docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot certonly --agree-tos --no-eff-email --email "$EMAIL_ACME" \
    --webroot -w /var/www/certbot \
    -d "$DOMAIN_CRM" -d "$DOMAIN_PBX"
  step "Reload nginx to pick up certificates"
  $COMPOSE exec nginx nginx -s reload || true
else
  step "Certificates already present; skipping issuance"
fi

# Show status
step "Stack status"
$COMPOSE ps

# Basic health checks
step "Basic HTTP checks"
curl -I "http://$DOMAIN_CRM/.well-known/acme-challenge/" || true
curl -I "https://$DOMAIN_CRM/" || true

step "Done. Access CRM at: https://$DOMAIN_CRM/ and Asterisk WS at: wss://$DOMAIN_PBX/ws"
