#!/bin/bash
# Health check script for Docker services

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}Django CRM Health Check${NC}"
echo -e "${BLUE}==================================${NC}"
echo ""

# Check if Docker is running
if ! docker ps > /dev/null 2>&1; then
    echo -e "${RED}✗ Docker is not running${NC}"
    exit 1
fi

# Check services
check_service() {
    local service=$1
    local container=$2
    
    if docker ps --format '{{.Names}}' | grep -q "$container"; then
        local status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null)
        if [ "$status" = "healthy" ] || [ -z "$status" ]; then
            echo -e "${GREEN}✓${NC} $service is running"
            return 0
        else
            echo -e "${YELLOW}⚠${NC} $service is running but unhealthy"
            return 1
        fi
    else
        echo -e "${RED}✗${NC} $service is not running"
        return 1
    fi
}

# Check all services
check_service "Redis" "crm_redis"
REDIS_OK=$?

check_service "PostgreSQL" "crm_postgres"
POSTGRES_OK=$?

check_service "Django Web" "crm_web"
WEB_OK=$?

check_service "Daphne WebSocket" "crm_daphne"
DAPHNE_OK=$?

check_service "Celery Worker" "crm_celery_worker"
CELERY_OK=$?

check_service "Nginx" "crm_nginx"
NGINX_OK=$?

echo ""
echo -e "${BLUE}Connectivity Tests:${NC}"

# Test Redis
if [ $REDIS_OK -eq 0 ]; then
    if docker exec crm_redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Redis responds to PING"
    else
        echo -e "${RED}✗${NC} Redis does not respond"
    fi
fi

# Test PostgreSQL
if [ $POSTGRES_OK -eq 0 ]; then
    if docker exec crm_postgres pg_isready -U "${POSTGRES_USER:-crm_user}" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} PostgreSQL is ready"
    else
        echo -e "${RED}✗${NC} PostgreSQL is not ready"
    fi
fi

# Test Django Web
if [ $WEB_OK -eq 0 ]; then
    if curl -f http://localhost:8000/ > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Django Web is accessible"
    else
        echo -e "${YELLOW}⚠${NC} Django Web is not accessible (may need login)"
    fi
fi

# Test WebSocket
if [ $DAPHNE_OK -eq 0 ]; then
    if curl -f http://localhost:8001/ > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Daphne WebSocket server is accessible"
    else
        echo -e "${YELLOW}⚠${NC} Daphne WebSocket server is not accessible"
    fi
fi

# Test Nginx
if [ $NGINX_OK -eq 0 ]; then
    if curl -f http://localhost/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Nginx proxy is accessible"
    else
        echo -e "${YELLOW}⚠${NC} Nginx proxy is not accessible"
    fi
fi

echo ""
echo -e "${BLUE}Resource Usage:${NC}"

# Show container stats
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | grep crm || echo "No containers found"

echo ""
echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}Health Check Complete${NC}"
echo -e "${BLUE}==================================${NC}"
