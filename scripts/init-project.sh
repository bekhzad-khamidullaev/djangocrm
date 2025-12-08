#!/bin/bash
# Initialize Django CRM project with Docker

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================${NC}"
echo -e "${BLUE}Django CRM Project Initialization${NC}"
echo -e "${BLUE}==================================${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${GREEN}✓ .env file created${NC}"
    echo -e "${YELLOW}⚠ Please edit .env with your settings before continuing${NC}"
    read -p "Press Enter to continue or Ctrl+C to exit..."
else
    echo -e "${GREEN}✓ .env file already exists${NC}"
fi

# Check Docker
echo -e "${YELLOW}Checking Docker installation...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed${NC}"
    exit 1
fi
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗ Docker Compose is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"

# Build images
echo ""
echo -e "${YELLOW}Building Docker images...${NC}"
docker-compose build

# Start services
echo ""
echo -e "${YELLOW}Starting services...${NC}"
docker-compose up -d

# Wait for services to be ready
echo ""
echo -e "${YELLOW}Waiting for services to be ready...${NC}"
sleep 10

# Check health
echo ""
echo -e "${YELLOW}Checking service health...${NC}"
./scripts/health-check.sh

# Run migrations
echo ""
echo -e "${YELLOW}Running database migrations...${NC}"
docker-compose exec -T web python manage.py migrate --noinput

# Collect static files
echo ""
echo -e "${YELLOW}Collecting static files...${NC}"
docker-compose exec -T web python manage.py collectstatic --noinput

# Create superuser
echo ""
echo -e "${YELLOW}Creating superuser...${NC}"
echo "Please enter superuser credentials:"
docker-compose exec web python manage.py createsuperuser

# Load demo data (optional)
echo ""
read -p "Do you want to load demo data? (y/n): " LOAD_DEMO
if [ "$LOAD_DEMO" = "y" ] || [ "$LOAD_DEMO" = "Y" ]; then
    echo -e "${YELLOW}Loading demo data...${NC}"
    docker-compose exec web python manage.py loaddata common/fixtures/sites.json
    docker-compose exec web python manage.py loaddata common/fixtures/department.json
    docker-compose exec web python manage.py loaddata crm/fixtures/country.json
    docker-compose exec web python manage.py loaddata crm/fixtures/currency.json
    echo -e "${GREEN}✓ Demo data loaded${NC}"
fi

# Success message
echo ""
echo -e "${GREEN}==================================${NC}"
echo -e "${GREEN}✓ Project Initialized!${NC}"
echo -e "${GREEN}==================================${NC}"
echo ""
echo -e "${BLUE}Access your CRM:${NC}"
echo -e "  Django Admin: ${GREEN}http://localhost:8000/admin/${NC}"
echo -e "  WebSocket Test: ${GREEN}http://localhost:8000/common/websocket-test/${NC}"
echo -e "  API: ${GREEN}http://localhost:8000/api/${NC}"
echo ""
echo -e "${BLUE}Useful commands:${NC}"
echo -e "  View logs: ${YELLOW}make logs${NC}"
echo -e "  Stop services: ${YELLOW}make down${NC}"
echo -e "  Restart services: ${YELLOW}make restart${NC}"
echo -e "  All commands: ${YELLOW}make help${NC}"
echo ""
echo -e "${GREEN}Happy CRM-ing! 🚀${NC}"
