#!/usr/bin/env bash
# Fast production deployment script for Django CRM + Asterisk (Docker Compose)
# Usage: sudo bash scripts/deplosh.sh [--app-dir /opt/djangocrm] [--email admin@example.com]
# Requires: Ubuntu 22.04+ (or compatible), root/sudo

set -euo pipefail
export DEBIAN_FRONTEND=noninteractive

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" # default = repo root
ACME_EMAIL="admin@windevs.uz"
DOMAIN_CRM="crm.windevs.uz"
DOMAIN_PBX="pbx.windevs.uz"
COMPOSE_FILE="docker-compose.production.yml"
COMPOSE="docker compose -f ${COMPOSE_FILE}"

NO_UFW=false
# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --app-dir)
      APP_DIR="$2"; shift 2;;
    --email)
      ACME_EMAIL="$2"; shift 2;;
    --no-ufw)
      NO_UFW=true; shift 1;;
    --help|-h)
      echo "Usage: sudo bash scripts/deplosh.sh [--app-dir /opt/djangocrm] [--email admin@example.com] [--no-ufw]"; exit 0;;
    *)
      echo "Unknown arg: $1"; exit 1;;
  esac
done

step() { echo -e "\n==== $* ===="; }
warn() { echo -e "[warn] $*"; }
info() { echo -e "[info] $*"; }

step "Summary"
echo "APP_DIR=${APP_DIR}"
echo "ACME_EMAIL=${ACME_EMAIL}"
echo "DOMAIN_CRM=${DOMAIN_CRM}"
echo "DOMAIN_PBX=${DOMAIN_PBX}"

step "Install Docker & Compose (if missing)"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release; echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  info "Docker already installed"
fi

step "Stop host services to free ports 80/443/5432"
systemctl disable --now nginx || true
systemctl disable --now postgresql || true
systemctl disable --now redis-server || true

step "Open firewall for HTTP(S)/SIP/RTP"
if [[ "${NO_UFW}" == "true" ]]; then
  warn "--no-ufw specified; skipping firewall config"
else
  if command -v ufw >/dev/null 2>&1; then
    ufw allow OpenSSH || true
    ufw allow 80/tcp || true
    ufw allow 443/tcp || true
    ufw allow 5060/tcp || true
    ufw allow 5060/udp || true
    ufw allow 10000:10100/udp || true
    ufw --force enable || true
    ufw status verbose || true
  else
    warn "ufw not found; skipping firewall config"
  fi
fi

step "Move to app directory"
cd "${APP_DIR}"

# Safety checks
if [[ ! -f ".env" ]]; then
  echo "ERROR: .env not found in ${APP_DIR}. Please copy .env.example to .env and adjust values." >&2
  exit 1
fi
if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "ERROR: ${COMPOSE_FILE} not found in ${APP_DIR}." >&2
  exit 1
fi

step "Set Asterisk external IP in .env (NAT/ICE)"
PUBIP=$(curl -s ifconfig.me || echo "")
if [[ -n "${PUBIP}" ]]; then
  if grep -q '^ASTERISK_EXTERNAL_IP=' .env; then
    sed -i "s/^ASTERISK_EXTERNAL_IP=.*/ASTERISK_EXTERNAL_IP=${PUBIP}/" .env
  else
    echo "ASTERISK_EXTERNAL_IP=${PUBIP}" >> .env
  fi
  info "ASTERISK_EXTERNAL_IP=${PUBIP}"
else
  warn "Could not detect public IP; keep existing ASTERISK_EXTERNAL_IP"
fi

step "Ensure certbot directories exist"
mkdir -p certbot/conf certbot/www

step "Build images (web, daphne, asterisk)"
${COMPOSE} build web daphne asterisk

step "Start postgres and redis"
${COMPOSE} up -d postgres redis

step "Wait briefly for services"
sleep 8
${COMPOSE} ps || true

step "Apply Django migrations"
${COMPOSE} run --rm web python manage.py migrate

step "Create superuser (press Ctrl+C to skip if already exists)"
${COMPOSE} run --rm web python manage.py createsuperuser || true

step "Collect static"
${COMPOSE} run --rm web python manage.py collectstatic --noinput

step "Start core services (asterisk, web, daphne, celery, beat, nginx)"
${COMPOSE} up -d asterisk web daphne celery celery-beat nginx

step "Initial TLS issuance if missing"
if [[ ! -d certbot/conf/live/${DOMAIN_CRM} || ! -d certbot/conf/live/${DOMAIN_PBX} ]]; then
  docker run --rm \
    -v "$(pwd)/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/certbot/www:/var/www/certbot" \
    certbot/certbot certonly --agree-tos --no-eff-email --email "${ACME_EMAIL}" \
    --webroot -w /var/www/certbot \
    -d "${DOMAIN_CRM}" -d "${DOMAIN_PBX}" || true
  ${COMPOSE} exec nginx nginx -s reload || true
else
  info "Certificates already exist; skipping issuance"
fi

step "Stack status"
${COMPOSE} ps || true

step "Basic HTTP(S) checks"
curl -I "https://${DOMAIN_CRM}/" || true
curl -I "https://${DOMAIN_PBX}/ws" || true

step "Tail last logs (nginx/web/daphne/asterisk)"
${COMPOSE} logs --tail=200 nginx web daphne asterisk || true

step "Done. Access CRM at: https://${DOMAIN_CRM}/ and Asterisk WS at: wss://${DOMAIN_PBX}/ws"
