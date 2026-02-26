# SmartToll Makefile — common development tasks
# Usage: make <target>
# Requires: docker, docker compose v2, python3

.PHONY: help up down build restart logs ps test test-billing test-processor \
        test-integration test-integration-up test-integration-down \
        shell-billing shell-processor shell-db migrate lint

# Default target
help:
	@echo "SmartToll development helpers"
	@echo ""
	@echo "  make up                  Build (if needed) and start all services"
	@echo "  make build               Rebuild all service images"
	@echo "  make down                Stop and remove all containers"
	@echo "  make restart             Stop, rebuild, and start all services"
	@echo "  make ps                  Show status of all services"
	@echo "  make logs                Follow logs for all services (Ctrl-C to stop)"
	@echo "  make logs-billing        Follow logs for the billing service"
	@echo "  make logs-processor      Follow logs for the toll processor"
	@echo ""
	@echo "  make test                Run all unit tests (billing + processor)"
	@echo "  make test-billing        Run billing service unit tests"
	@echo "  make test-processor      Run toll processor unit tests"
	@echo "  make test-integration    Run integration tests (requires running stack)"
	@echo ""
	@echo "  make shell-billing       Open a shell in the billing container"
	@echo "  make shell-processor     Open a shell in the toll processor container"
	@echo "  make shell-db            Open a psql shell in the database container"
	@echo "  make migrate             Run Alembic migrations inside the billing container"

# ---- Docker Compose ----

up:
	docker compose up -d

build:
	docker compose build

down:
	docker compose down --remove-orphans

restart: down build up

ps:
	docker compose ps

logs:
	docker compose logs -f

logs-billing:
	docker compose logs -f billing_service

logs-processor:
	docker compose logs -f toll_processor

# ---- Unit Tests ----

test: test-billing test-processor

test-billing:
	@echo "=== Billing Service unit tests ==="
	cd billing_service && python -m pytest tests/ -v

test-processor:
	@echo "=== Toll Processor unit tests ==="
	cd toll_processor && python -m pytest tests/ -v

# ---- Integration Tests ----
# The integration stack (Kafka, Redis, Postgres + app services) must be started first.
# These targets manage it for you.

test-integration-up:
	@echo "=== Starting integration test stack ==="
	docker compose -f tests/integration/docker-compose.integration.yml up -d

test-integration-down:
	@echo "=== Stopping integration test stack ==="
	docker compose -f tests/integration/docker-compose.integration.yml down --remove-orphans

test-integration: test-integration-up
	@echo "=== Waiting 30 s for services to become healthy ==="
	sleep 30
	@echo "=== Integration tests ==="
	python -m pytest tests/integration/ -v; \
	EXIT=$$?; \
	$(MAKE) test-integration-down; \
	exit $$EXIT

# ---- Convenience ----

shell-billing:
	docker compose exec billing_service /bin/bash

shell-processor:
	docker compose exec toll_processor /bin/bash

shell-db:
	docker compose exec postgres psql -U $$POSTGRES_USER -d $$POSTGRES_DB

migrate:
	docker compose exec billing_service alembic upgrade head
