#!/bin/bash
# Backup script for Django CRM Docker deployment

set -e

# Configuration
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
POSTGRES_CONTAINER="crm_postgres"
REDIS_CONTAINER="crm_redis"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}Django CRM Backup Script${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL
echo -e "${YELLOW}Backing up PostgreSQL database...${NC}"
if docker ps --format '{{.Names}}' | grep -q "$POSTGRES_CONTAINER"; then
    docker exec "$POSTGRES_CONTAINER" pg_dump -U "${POSTGRES_USER:-crm_user}" "${POSTGRES_DB:-crm_db}" | gzip > "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"
    echo -e "${GREEN}✓ PostgreSQL backup created: postgres_${TIMESTAMP}.sql.gz${NC}"
else
    echo -e "${RED}✗ PostgreSQL container not running${NC}"
fi

# Backup Redis
echo -e "${YELLOW}Backing up Redis data...${NC}"
if docker ps --format '{{.Names}}' | grep -q "$REDIS_CONTAINER"; then
    docker exec "$REDIS_CONTAINER" redis-cli SAVE
    docker cp "$REDIS_CONTAINER:/data/dump.rdb" "$BACKUP_DIR/redis_${TIMESTAMP}.rdb"
    echo -e "${GREEN}✓ Redis backup created: redis_${TIMESTAMP}.rdb${NC}"
else
    echo -e "${RED}✗ Redis container not running${NC}"
fi

# Backup media files
echo -e "${YELLOW}Backing up media files...${NC}"
if [ -d "./media" ]; then
    tar -czf "$BACKUP_DIR/media_${TIMESTAMP}.tar.gz" ./media
    echo -e "${GREEN}✓ Media backup created: media_${TIMESTAMP}.tar.gz${NC}"
else
    echo -e "${YELLOW}⚠ Media directory not found${NC}"
fi

# List backups
echo ""
echo -e "${GREEN}Backup completed!${NC}"
echo -e "${YELLOW}Backup location: $BACKUP_DIR${NC}"
echo ""
echo "Recent backups:"
ls -lh "$BACKUP_DIR" | tail -5

# Cleanup old backups (keep last 7 days)
echo ""
echo -e "${YELLOW}Cleaning up old backups (older than 7 days)...${NC}"
find "$BACKUP_DIR" -name "*.gz" -type f -mtime +7 -delete
find "$BACKUP_DIR" -name "*.rdb" -type f -mtime +7 -delete
echo -e "${GREEN}✓ Cleanup completed${NC}"

echo ""
echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}Backup process finished!${NC}"
echo -e "${GREEN}==================================${NC}"
