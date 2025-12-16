#!/usr/bin/env bash
set -euo pipefail
COMPOSE="docker compose -f docker-compose.production.yml"

check() { local name=$1; shift; echo -n "[check] $name ... "; if "$@" >/dev/null 2>&1; then echo OK; else echo FAIL; fi }

$COMPOSE ps

check postgres_running docker ps --format '{{.Names}}' | grep -q '^crm_postgres$'
check redis_running docker ps --format '{{.Names}}' | grep -q '^crm_redis$'
check web_running docker ps --format '{{.Names}}' | grep -q '^crm_web$'
check daphne_running docker ps --format '{{.Names}}' | grep -q '^crm_daphne$'
check celery_running docker ps --format '{{.Names}}' | grep -q '^crm_celery$'
check celerybeat_running docker ps --format '{{.Names}}' | grep -q '^crm_celery_beat$'
check nginx_running docker ps --format '{{.Names}}' | grep -q '^crm_nginx$'
check asterisk_running docker ps --format '{{.Names}}' | grep -q '^crm_asterisk$'

# HTTP(S) checks
CRM_DOMAIN=${1:-crm.windevs.uz}
PBX_DOMAIN=${2:-pbx.windevs.uz}

check crm_http curl -f -I "http://$CRM_DOMAIN/.well-known/acme-challenge/"
check crm_https curl -f -I "https://$CRM_DOMAIN/"
check pbx_ws curl -f -I "https://$PBX_DOMAIN/ws"

# Redis ping
check redis_ping docker exec crm_redis redis-cli ping
# Postgres ready
check postgres_ready docker exec crm_postgres pg_isready -U "${POSTGRES_USER:-crm_user}"
# Asterisk version
check asterisk_cli docker exec -u asterisk crm_asterisk asterisk -rx 'core show version'

echo "Health checks complete."