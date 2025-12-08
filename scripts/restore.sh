#!/bin/bash
# Restore script for Django CRM Docker deployment

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
POSTGRES_CONTAINER="crm_postgres"
REDIS_CONTAINER="crm_redis"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}Django CRM Restore Script${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""

# Check if backup directory exists
if [ ! -d "$BACKUP_DIR" ]; then
    echo -e "${RED}✗ Backup directory not found: $BACKUP_DIR${NC}"
    exit 1
fi

# List available backups
echo -e "${YELLOW}Available backups:${NC}"
echo ""
echo "PostgreSQL backups:"
ls -lh "$BACKUP_DIR"/postgres_*.sql.gz 2>/dev/null || echo "  No PostgreSQL backups found"
echo ""
echo "Redis backups:"
ls -lh "$BACKUP_DIR"/redis_*.rdb 2>/dev/null || echo "  No Redis backups found"
echo ""
echo "Media backups:"
ls -lh "$BACKUP_DIR"/media_*.tar.gz 2>/dev/null || echo "  No media backups found"
echo ""

# Ask user which backup to restore
read -p "Enter backup timestamp (e.g., 20240115_120000) or 'latest': " TIMESTAMP

if [ "$TIMESTAMP" = "latest" ]; then
    POSTGRES_BACKUP=$(ls -t "$BACKUP_DIR"/postgres_*.sql.gz 2>/dev/null | head -1)
    REDIS_BACKUP=$(ls -t "$BACKUP_DIR"/redis_*.rdb 2>/dev/null | head -1)
    MEDIA_BACKUP=$(ls -t "$BACKUP_DIR"/media_*.tar.gz 2>/dev/null | head -1)
else
    POSTGRES_BACKUP="$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"
    REDIS_BACKUP="$BACKUP_DIR/redis_${TIMESTAMP}.rdb"
    MEDIA_BACKUP="$BACKUP_DIR/media_${TIMESTAMP}.tar.gz"
fi

# Confirmation
echo ""
echo -e "${YELLOW}The following backups will be restored:${NC}"
echo "PostgreSQL: $POSTGRES_BACKUP"
echo "Redis: $REDIS_BACKUP"
echo "Media: $MEDIA_BACKUP"
echo ""
read -p "Are you sure? This will OVERWRITE current data! (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${RED}Restore cancelled${NC}"
    exit 0
fi

# Restore PostgreSQL
if [ -f "$POSTGRES_BACKUP" ]; then
    echo -e "${YELLOW}Restoring PostgreSQL database...${NC}"
    if docker ps --format '{{.Names}}' | grep -q "$POSTGRES_CONTAINER"; then
        gunzip -c "$POSTGRES_BACKUP" | docker exec -i "$POSTGRES_CONTAINER" psql -U "${POSTGRES_USER:-crm_user}" "${POSTGRES_DB:-crm_db}"
        echo -e "${GREEN}✓ PostgreSQL restored${NC}"
    else
        echo -e "${RED}✗ PostgreSQL container not running${NC}"
    fi
else
    echo -e "${YELLOW}⚠ PostgreSQL backup not found, skipping${NC}"
fi

# Restore Redis
if [ -f "$REDIS_BACKUP" ]; then
    echo -e "${YELLOW}Restoring Redis data...${NC}"
    if docker ps --format '{{.Names}}' | grep -q "$REDIS_CONTAINER"; then
        docker cp "$REDIS_BACKUP" "$REDIS_CONTAINER:/data/dump.rdb"
        docker restart "$REDIS_CONTAINER"
        echo -e "${GREEN}✓ Redis restored and restarted${NC}"
    else
        echo -e "${RED}✗ Redis container not running${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Redis backup not found, skipping${NC}"
fi

# Restore media files
if [ -f "$MEDIA_BACKUP" ]; then
    echo -e "${YELLOW}Restoring media files...${NC}"
    tar -xzf "$MEDIA_BACKUP"
    echo -e "${GREEN}✓ Media files restored${NC}"
else
    echo -e "${YELLOW}⚠ Media backup not found, skipping${NC}"
fi

echo ""
echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}Restore process finished!${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""
echo -e "${YELLOW}Don't forget to restart services:${NC}"
echo "  docker-compose restart"
