#!/bin/bash
set -e

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL..."
until PGPASSWORD=$ASTERISK_DB_PASSWORD psql -h "$ASTERISK_DB_HOST" -U "$ASTERISK_DB_USER" -d "$ASTERISK_DB_NAME" -c '\q' 2>/dev/null; do
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

echo "Starting Asterisk..."
exec "$@"
