#!/bin/bash
set -e

# Ensure required directories are owned by asterisk (especially when mounted as volumes)
mkdir -p /var/log/asterisk /var/lib/asterisk /var/spool/asterisk /etc/asterisk /var/run/asterisk
chown -R asterisk:asterisk /var/log/asterisk /var/lib/asterisk /var/spool/asterisk /var/run/asterisk

# Wait for PostgreSQL to be ready if vars are provided
if [[ -n "$ASTERISK_DB_HOST" && -n "$ASTERISK_DB_USER" && -n "$ASTERISK_DB_NAME" && -n "$ASTERISK_DB_PASSWORD" ]]; then
  echo "Waiting for PostgreSQL..."
  until PGPASSWORD=$ASTERISK_DB_PASSWORD psql -h "$ASTERISK_DB_HOST" -U "$ASTERISK_DB_USER" -d "$ASTERISK_DB_NAME" -c '\\q' 2>/dev/null; do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 2
  done
  echo "PostgreSQL is up - configuring Asterisk"

  # Configure ODBC connection
  cat > /etc/odbc.ini <<EOF
[PostgreSQL-asterisk]
Description = PostgreSQL Asterisk Realtime
Driver = PostgreSQL Unicode
Database = ${ASTERISK_DB_NAME}
Servername = ${ASTERISK_DB_HOST}
UserName = ${ASTERISK_DB_USER}
Password = ${ASTERISK_DB_PASSWORD}
Port = ${ASTERISK_DB_PORT:-5432}
Protocol = 9.0
ReadOnly = No
RowVersioning = No
ShowSystemTables = No
ShowOidColumn = No
FakeOidIndex = No
ConnSettings =
EOF

  # Configure res_odbc.conf
  cat > /etc/asterisk/res_odbc.conf <<EOF
[asterisk-rt]
enabled => yes
dsn => PostgreSQL-asterisk
username => ${ASTERISK_DB_USER}
password => ${ASTERISK_DB_PASSWORD}
pre-connect => yes
max_connections => 20
EOF

  # Configure AMI
  cat > /etc/asterisk/manager.conf <<EOF
[general]
enabled = yes
port = 5038
bindaddr = 0.0.0.0

[${ASTERISK_AMI_USERNAME:-admin}]
secret = ${ASTERISK_AMI_SECRET:-changeme}
deny = 0.0.0.0/0.0.0.0
permit = 0.0.0.0/0.0.0.0
read = system,call,log,verbose,command,agent,user,config,command,dtmf,reporting,cdr,dialplan,originate
write = system,call,log,verbose,command,agent,user,config,command,dtmf,reporting,cdr,dialplan,originate
writetimeout = 5000
EOF

  # Set permissions
  chown asterisk:asterisk /etc/odbc.ini
  chown asterisk:asterisk /etc/asterisk/res_odbc.conf
  chown asterisk:asterisk /etc/asterisk/manager.conf
  chmod 640 /etc/odbc.ini
  chmod 640 /etc/asterisk/res_odbc.conf
  chmod 640 /etc/asterisk/manager.conf

  # Configure CDR via ODBC (env-driven)
  CDR_ENABLE_LOWER=$(echo "${CDR_ENABLE:-true}" | tr '[:upper:]' '[:lower:]')
  CEL_ENABLE_LOWER=$(echo "${CEL_ENABLE:-true}" | tr '[:upper:]' '[:lower:]')
  CDR_BATCH_SIZE_VAL=${CDR_BATCH_SIZE:-100}
  CDR_UNANSWERED_VAL=$(echo "${CDR_UNANSWERED:-no}" | tr '[:upper:]' '[:lower:]')

  if [[ "$CDR_ENABLE_LOWER" == "true" || "$CDR_ENABLE_LOWER" == "1" || "$CDR_ENABLE_LOWER" == "yes" || -z "$CDR_ENABLE_LOWER" ]]; then
    cat > /etc/asterisk/cdr.conf <<EOF
[general]
enable = yes
unanswered = ${CDR_UNANSWERED_VAL}
hasexten = yes
batch = yes
size = ${CDR_BATCH_SIZE_VAL}
safe_shutdown = yes
EOF

    cat > /etc/asterisk/cdr_odbc.conf <<EOF
[global]
dsn = PostgreSQL-asterisk
loguniqueid = yes
table = cdr
usegmtime = no
dispositionstring = yes
usecallerid = yes
EOF
  else
    cat > /etc/asterisk/cdr.conf <<EOF
[general]
enable = no
EOF
  fi

  # Configure CEL via ODBC (env-driven)
  if [[ "$CEL_ENABLE_LOWER" == "true" || "$CEL_ENABLE_LOWER" == "1" || "$CEL_ENABLE_LOWER" == "yes" || -z "$CEL_ENABLE_LOWER" ]]; then
    cat > /etc/asterisk/cel.conf <<EOF
[general]
enable = yes
apps = all
events = ALL
EOF

    cat > /etc/asterisk/cel_odbc.conf <<EOF
[global]
dsn = PostgreSQL-asterisk
table = cel
usegmtime = no
EOF
  else
    cat > /etc/asterisk/cel.conf <<EOF
[general]
enable = no
EOF
  fi

  chown asterisk:asterisk /etc/asterisk/cdr.conf /etc/asterisk/cdr_odbc.conf /etc/asterisk/cel.conf /etc/asterisk/cel_odbc.conf 2>/dev/null || true
  chmod 640 /etc/asterisk/cdr.conf /etc/asterisk/cdr_odbc.conf /etc/asterisk/cel.conf /etc/asterisk/cel_odbc.conf 2>/dev/null || true

  # Background cleanup loop for CDR/CEL retention
  (
    set -e
    CDR_RET_DAYS=${CDR_RETENTION_DAYS:-90}
    CEL_RET_DAYS=${CEL_RETENTION_DAYS:-90}
    while true; do
      if [[ -n "$ASTERISK_DB_HOST" && -n "$ASTERISK_DB_USER" && -n "$ASTERISK_DB_NAME" ]]; then
        # Clean CDR older than X days
        if [[ "$CDR_RET_DAYS" =~ ^[0-9]+$ ]] && [[ "$CDR_RET_DAYS" -gt 0 ]]; then
          PGPASSWORD=$ASTERISK_DB_PASSWORD psql -h "$ASTERISK_DB_HOST" -U "$ASTERISK_DB_USER" -d "$ASTERISK_DB_NAME" -c "DELETE FROM cdr WHERE calldate < NOW() - INTERVAL '${CDR_RET_DAYS} days';" || true
        fi
        # Clean CEL older than X days
        if [[ "$CEL_RET_DAYS" =~ ^[0-9]+$ ]] && [[ "$CEL_RET_DAYS" -gt 0 ]]; then
          PGPASSWORD=$ASTERISK_DB_PASSWORD psql -h "$ASTERISK_DB_HOST" -U "$ASTERISK_DB_USER" -d "$ASTERISK_DB_NAME" -c "DELETE FROM cel WHERE eventtime < NOW() - INTERVAL '${CEL_RET_DAYS} days';" || true
        fi
      fi
      sleep 86400
    done
  ) & disown

fi

# TLS certificate preparation (optional)
if [[ -n "$ASTERISK_TLS_CERT" && -n "$ASTERISK_TLS_KEY" ]]; then
  mkdir -p /etc/asterisk/keys
  if [[ -f "$ASTERISK_TLS_CERT" && -f "$ASTERISK_TLS_KEY" ]]; then
    cp "$ASTERISK_TLS_CERT" /etc/asterisk/keys/asterisk.pem || true
    cp "$ASTERISK_TLS_KEY" /etc/asterisk/keys/asterisk.key || true
    chown -R asterisk:asterisk /etc/asterisk/keys
    chmod 600 /etc/asterisk/keys/asterisk.key || true
  else
    echo "Warning: TLS files not found at ASTERISK_TLS_CERT/ASTERISK_TLS_KEY paths"
  fi
fi

# Alerting helpers (webhook and/or email via msmtp)
send_alert() {
  SUBJECT="$1"
  BODY="$2"
  # Webhook first if configured
  if [[ -n "$ALERT_WEBHOOK_URL" ]]; then
    curl -sS -X POST "$ALERT_WEBHOOK_URL" -H 'Content-Type: application/json' \
      -d "{\"subject\":$(printf '%s' "$SUBJECT" | jq -Rs .),\"message\":$(printf '%s' "$BODY" | jq -Rs .),\"source\":\"asterisk-cleaner\"}" || true
  fi
  # Email via msmtp if enabled
  ALERT_EMAIL_ENABLE_LOWER=$(echo "${ALERT_EMAIL_ENABLE:-false}" | tr '[:upper:]' '[:lower:]')
  if [[ "$ALERT_EMAIL_ENABLE_LOWER" == "true" || "$ALERT_EMAIL_ENABLE_LOWER" == "1" || "$ALERT_EMAIL_ENABLE_LOWER" == "yes" ]]; then
    if [[ -n "$SMTP_HOST" && -n "$ALERT_EMAIL_TO" ]]; then
      cat > /etc/msmtprc <<EOF
account default
host ${SMTP_HOST}
port ${SMTP_PORT:-587}
auth ${SMTP_AUTH_METHOD:-on}
user ${SMTP_USER:-}
password ${SMTP_PASSWORD:-}
tls ${SMTP_TLS:-on}
tls_starttls ${SMTP_STARTTLS:-on}
from ${ALERT_EMAIL_FROM:-asterisk@localhost}
logfile /var/log/asterisk/msmtp.log
EOF
      chmod 600 /etc/msmtprc
      printf "To: %s\nFrom: %s\nSubject: %s\n\n%s\n" "${ALERT_EMAIL_TO}" "${ALERT_EMAIL_FROM:-asterisk@localhost}" "$SUBJECT" "$BODY" | msmtp -a default -t || true
    fi
  fi
}

# Growth thresholds (counts over last 24h)
CDR_GROWTH_THRESHOLD=${CDR_GROWTH_THRESHOLD:-0}
CEL_GROWTH_THRESHOLD=${CEL_GROWTH_THRESHOLD:-0}
CLEANUP_INTERVAL_SECONDS=${CLEANUP_INTERVAL_SECONDS:-86400}

# After TLS preparation, start Asterisk with privilege drop

echo "Starting Asterisk..."
# Drop privileges to the asterisk user
exec gosu asterisk "$@" &
ASTERISK_PID=$!

# Run cleanup/growth monitor in background as root and exit if Asterisk stops
(
  while kill -0 "$ASTERISK_PID" 2>/dev/null; do
    if [[ -n "$ASTERISK_DB_HOST" && -n "$ASTERISK_DB_USER" && -n "$ASTERISK_DB_NAME" ]]; then
      # Cleanup
      CDR_RET_DAYS=${CDR_RETENTION_DAYS:-90}
      CEL_RET_DAYS=${CEL_RETENTION_DAYS:-90}
      if [[ "$CDR_RET_DAYS" =~ ^[0-9]+$ ]] && [[ "$CDR_RET_DAYS" -gt 0 ]]; then
        if ! PGPASSWORD=$ASTERISK_DB_PASSWORD psql -h "$ASTERISK_DB_HOST" -U "$ASTERISK_DB_USER" -d "$ASTERISK_DB_NAME" -c "DELETE FROM cdr WHERE calldate < NOW() - INTERVAL '${CDR_RET_DAYS} days';"; then
          send_alert "Asterisk CDR cleanup failed" "Failed to cleanup CDR older than ${CDR_RET_DAYS} days on ${HOSTNAME}" || true
        fi
      fi
      if [[ "$CEL_RET_DAYS" =~ ^[0-9]+$ ]] && [[ "$CEL_RET_DAYS" -gt 0 ]]; then
        if ! PGPASSWORD=$ASTERISK_DB_PASSWORD psql -h "$ASTERISK_DB_HOST" -U "$ASTERISK_DB_USER" -d "$ASTERISK_DB_NAME" -c "DELETE FROM cel WHERE eventtime < NOW() - INTERVAL '${CEL_RET_DAYS} days';"; then
          send_alert "Asterisk CEL cleanup failed" "Failed to cleanup CEL older than ${CEL_RET_DAYS} days on ${HOSTNAME}" || true
        fi
      fi
      # Growth checks (last 24h)
      if [[ "$CDR_GROWTH_THRESHOLD" =~ ^[0-9]+$ ]] && [[ "$CDR_GROWTH_THRESHOLD" -gt 0 ]]; then
        CDR_24H=$(PGPASSWORD=$ASTERISK_DB_PASSWORD psql -h "$ASTERISK_DB_HOST" -U "$ASTERISK_DB_USER" -d "$ASTERISK_DB_NAME" -t -A -c "SELECT COALESCE(COUNT(*),0) FROM cdr WHERE calldate > NOW() - INTERVAL '1 day';" || echo 0)
        if [[ "$CDR_24H" =~ ^[0-9]+$ ]] && (( CDR_24H > CDR_GROWTH_THRESHOLD )); then
          send_alert "Asterisk CDR growth warning" "CDR rows in last 24h: ${CDR_24H} exceeded threshold ${CDR_GROWTH_THRESHOLD} on ${HOSTNAME}" || true
        fi
      fi
      if [[ "$CEL_GROWTH_THRESHOLD" =~ ^[0-9]+$ ]] && [[ "$CEL_GROWTH_THRESHOLD" -gt 0 ]]; then
        CEL_24H=$(PGPASSWORD=$ASTERISK_DB_PASSWORD psql -h "$ASTERISK_DB_HOST" -U "$ASTERISK_DB_USER" -d "$ASTERISK_DB_NAME" -t -A -c "SELECT COALESCE(COUNT(*),0) FROM cel WHERE eventtime > NOW() - INTERVAL '1 day';" || echo 0)
        if [[ "$CEL_24H" =~ ^[0-9]+$ ]] && (( CEL_24H > CEL_GROWTH_THRESHOLD )); then
          send_alert "Asterisk CEL growth warning" "CEL rows in last 24h: ${CEL_24H} exceeded threshold ${CEL_GROWTH_THRESHOLD} on ${HOSTNAME}" || true
        fi
      fi
    fi
    sleep "$CLEANUP_INTERVAL_SECONDS"
  done
) &

# Wait for Asterisk
wait "$ASTERISK_PID"
