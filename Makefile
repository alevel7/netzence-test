.PHONY: help build up down down-v restart logs logs-web test lint format migrate makemigrations shell-web shell-db shell-redis clean

# Default target
help:
	@echo "======================================================================"
	@echo "FastAPI + PostgreSQL + Redis Orchestration Commands"
	@echo "======================================================================"
	@echo "  make up             Start all services in background (docker compose up -d)"
	@echo "  make down           Stop all services (docker compose down)"
	@echo "  make down-v         Stop and delete volumes (warning: deletes DB data)"
	@echo "  make build          Build or rebuild Docker images"
	@echo "  make restart        Restart all services"
	@echo "  make logs           Follow logs of all containers"
	@echo "  make logs-web       Follow logs of web application container"
	@echo "  make test           Run test suite with pytest"
	@echo "  make migrate        Apply pending database migrations (alembic upgrade head)"
	@echo "  make makemigrations Generate new migration (e.g. make makemigrations m='add_field')"
	@echo "  make shell-web      Open interactive bash shell inside web container"
	@echo "  make shell-db       Open psql prompt inside database container"
	@echo "  make shell-redis    Open redis-cli inside Redis container"
	@echo "  make clean          Remove Python cache and compiled files"
	@echo "======================================================================"

build:
	docker compose build

up:
	docker compose up -d --build

down:
	docker compose down

down-v:
	docker compose down -v

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-web:
	docker compose logs -f web

test:
	docker compose exec web pytest -v

lint:
	ruff check .

format:
	ruff format .

migrate:
	docker compose exec web alembic upgrade head

makemigrations:
	docker compose exec web alembic revision --autogenerate -m "$(or $(m),auto_migration)"

shell-web:
	docker compose exec web /bin/bash

shell-db:
	docker compose exec db psql -U postgres -d app_db

shell-redis:
	docker compose exec redis redis-cli

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".coverage" -delete

