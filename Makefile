.PHONY: help build up down restart logs shell test clean migrate createsuperuser

# Default target
help:
	@echo "Django CRM Docker Commands"
	@echo "=========================="
	@echo ""
	@echo "Development:"
	@echo "  make dev-up          - Start development environment"
	@echo "  make dev-down        - Stop development environment"
	@echo "  make dev-logs        - Show development logs"
	@echo "  make dev-shell       - Open Django shell"
	@echo ""
	@echo "Production:"
	@echo "  make build           - Build Docker images"
	@echo "  make up              - Start production environment"
	@echo "  make down            - Stop production environment"
	@echo "  make restart         - Restart all services"
	@echo "  make logs            - Show all logs"
	@echo "  make logs-web        - Show web logs"
	@echo "  make logs-daphne     - Show Daphne logs"
	@echo "  make logs-celery     - Show Celery logs"
	@echo ""
	@echo "Database:"
	@echo "  make migrate         - Run migrations"
	@echo "  make makemigrations  - Create migrations"
	@echo "  make createsuperuser - Create superuser"
	@echo "  make dbshell         - Open database shell"
	@echo ""
	@echo "Utilities:"
	@echo "  make shell           - Open Django shell"
	@echo "  make bash            - Open bash in web container"
	@echo "  make test            - Run tests"
	@echo "  make collectstatic   - Collect static files"
	@echo "  make clean           - Clean up containers and volumes"
	@echo "  make ps              - Show running containers"
	@echo ""

# Development environment
dev-up:
	docker-compose -f docker-compose.dev.yml up -d
	@echo "Development environment started!"
	@echo "Django: http://localhost:8000"
	@echo "Daphne: ws://localhost:8001"
	@echo "Redis Commander: http://localhost:8081"

dev-down:
	docker-compose -f docker-compose.dev.yml down

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-shell:
	docker-compose -f docker-compose.dev.yml exec web python manage.py shell

# Production environment
build:
	docker-compose build

up:
	docker-compose up -d
	@echo "Production environment started!"
	@echo "Nginx: http://localhost"
	@echo "Django: http://localhost:8000"
	@echo "Daphne: ws://localhost:8001"

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-web:
	docker-compose logs -f web

logs-daphne:
	docker-compose logs -f daphne

logs-celery:
	docker-compose logs -f celery_worker

# Database operations
migrate:
	docker-compose exec web python manage.py migrate

makemigrations:
	docker-compose exec web python manage.py makemigrations

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

dbshell:
	docker-compose exec web python manage.py dbshell

# Utilities
shell:
	docker-compose exec web python manage.py shell

bash:
	docker-compose exec web /bin/bash

test:
	docker-compose exec web pytest -v

test-coverage:
	docker-compose exec web pytest --cov=. --cov-report=html --cov-report=term -v

test-local:
	pytest -v

test-local-coverage:
	pytest --cov=. --cov-report=html --cov-report=term -v

lint:
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=migrations,venv,env,.git,__pycache__
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics --exclude=migrations,venv,env,.git,__pycache__

format:
	black --exclude='/(migrations|venv|env|\.git|__pycache__|node_modules)/' .
	isort --skip migrations --skip venv --skip env .

format-check:
	black --check --exclude='/(migrations|venv|env|\.git|__pycache__|node_modules)/' .
	isort --check-only --skip migrations --skip venv --skip env .

collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

ps:
	docker-compose ps

# Cleanup
clean:
	docker-compose down -v
	docker system prune -f

clean-all:
	docker-compose down -v --rmi all
	docker system prune -af

# Redis commands
redis-cli:
	docker-compose exec redis redis-cli

redis-monitor:
	docker-compose exec redis redis-cli monitor

# Testing WebSocket
test-ws:
	@echo "Testing WebSocket connection..."
	@echo "Open http://localhost:8000/common/websocket-test/ in your browser"

# Environment setup
setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo ".env file created. Please edit it with your settings."; \
	else \
		echo ".env file already exists."; \
	fi

# Initialize project
init: setup build up migrate
	@echo "Project initialized!"
	@echo "Create a superuser with: make createsuperuser"
