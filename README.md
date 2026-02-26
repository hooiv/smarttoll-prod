# SmartToll - Toll Processing System

A modern, scalable microservices architecture for processing GPS data from vehicles, calculating toll charges, and handling billing.

## System Overview

SmartToll consists of three main components:

1. **OBU Simulator**: Generates simulated GPS data from vehicles and publishes it to Kafka.
2. **Toll Processor**: Processes real-time GPS data, detects when vehicles enter/exit toll zones, and calculates toll charges.
3. **Billing Service**: Handles toll event consumption, payment processing, and provides a REST API for transaction status.

## Tech Stack

- **Messaging**: Apache Kafka (with Zookeeper)
- **Cache**: Redis 7
- **Database**: PostgreSQL 15 with PostGIS extension
- **API**: FastAPI + Uvicorn (Billing Service)
- **Observability**: Prometheus metrics on every service
- **Container Orchestration**: Docker Compose

## Prerequisites

- Docker & Docker Compose v2 (`docker compose` CLI)
- Python 3.11+ (only needed for local non-Docker development)

## Quick Start (Docker Compose)

```bash
# 1. Create .env from the template
cp .env.example .env

# 2. Build and start all services (single command — reliable from a cold start)
docker compose up -d

# 3. Verify all 7 services are healthy
docker compose ps
```

Services are available at:

| Service | URL |
|---|---|
| Billing API (Swagger UI) | http://localhost:8001/docs |
| Billing liveness | http://localhost:8001/api/v1/health/live |
| Billing readiness | http://localhost:8001/api/v1/health/ready |
| Billing Prometheus metrics | http://localhost:8001/metrics |
| Toll Processor liveness | http://localhost:8080/health/live |
| Toll Processor Prometheus metrics | http://localhost:8081/ |

## Environment Variables

All configuration lives in the root `.env` file. See `.env.example` for the full list with documentation. Key variables:

```ini
# Postgres
POSTGRES_DB=smarttoll_dev
POSTGRES_USER=smarttoll_user
POSTGRES_PASSWORD=changeme_in_prod_123!

# Billing API authentication (required)
SERVICE_API_KEY=supersecretapikey123

# Optional tuning
LOG_LEVEL=INFO
MOCK_PAYMENT_FAIL_RATE=0.1   # 0.0 = always succeed, 1.0 = always fail
```

## Running Locally (Without Docker)

### Linux / macOS
```bash
cp .env.example .env
docker compose up -d zookeeper kafka redis postgres   # infrastructure only
./run_local.sh                                        # Python services in background
```

### Windows (PowerShell)
```powershell
Copy-Item .env.example .env
docker compose up -d zookeeper kafka redis postgres
.\run_local.ps1
```

## Running Unit Tests

```bash
# Using the Makefile (recommended)
make test

# Or directly from each service directory
cd billing_service && pytest tests/ -v
cd toll_processor  && pytest tests/ -v
```

## Running Integration Tests

```bash
# Using the Makefile — starts the stack, waits, runs tests, then tears down
make test-integration

# Or manually
docker compose -f tests/integration/docker-compose.integration.yml up -d
sleep 30  # wait for services to be healthy
pytest tests/integration/ -v
docker compose -f tests/integration/docker-compose.integration.yml down
```

## Deploying to Production

1. Push images to your registry:
   ```bash
   docker tag smarttoll-prod-billing_service  my-registry/billing_service:1.0.0
   docker tag smarttoll-prod-toll_processor   my-registry/toll_processor:1.0.0
   docker push my-registry/billing_service:1.0.0
   docker push my-registry/toll_processor:1.0.0
   ```
2. Provision external Kafka, Redis, and PostgreSQL (PostGIS) instances.
3. Deploy with your orchestrator (Kubernetes, ECS, Fly.io, …):
   - **Liveness** probe: `GET /api/v1/health/live` (billing) or `GET /health/live` (processor)
   - **Readiness** probe: `GET /api/v1/health/ready` (billing) or `GET /health/ready` (processor)
   - **Prometheus** scrape: `/metrics` (billing, port 8000) or port `8081` (processor)
4. Set all required env vars as secrets in your orchestrator.

---

## Architecture Diagram

```
+----------------+      +-------------------+      +-------------------+
|  OBU Simulator | ---> |   Kafka Broker    | ---> |   Toll Processor  |
+----------------+      |  (GPS raw topic)  |      |  (geofence logic) |
                         +-------------------+      +--------+----------+
                                |                            |
                         (toll events topic)        Redis (vehicle state)
                                |                  Postgres+PostGIS (zones)
                         +------v------------+
                         |  Billing Service  |
                         |  (FastAPI + async |
                         |   Kafka consumer) |
                         +-------------------+
                                |
                         Postgres (billing_transactions)
```

---

## API Reference

The Billing Service exposes a REST API documented with OpenAPI/Swagger:

- **Swagger UI**: http://localhost:8001/docs
- **ReDoc**: http://localhost:8001/redoc

All `*/transactions*` endpoints require the `X-API-KEY` request header.
Every response includes an `X-Request-ID` header for distributed tracing.

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/v1/health/live` | — | Liveness probe |
| GET | `/api/v1/health/ready` | — | Readiness probe (checks DB + Kafka consumer) |
| GET | `/api/v1/version` | — | Service version |
| GET | `/api/v1/transactions` | ✓ | List transactions (filter by `vehicle_id`, `status`; paginated) |
| GET | `/api/v1/transactions/{id}` | ✓ | Get transaction by internal ID |
| GET | `/api/v1/transactions/status/{toll_event_id}` | ✓ | Get transaction by Toll Event ID |
| GET | `/metrics` | — | Prometheus metrics |

Transaction responses include: `id`, `toll_event_id`, `vehicle_id`, `amount`, `currency`, `status`, `retry_count`, `transaction_time`, `last_updated`, `payment_gateway_ref`, `error_message`.

---

## Contributing

1. Fork the repository and create a feature branch.
2. Install dev dependencies: `pip install -r requirements-dev.txt`
3. Run unit tests: `cd billing_service && pytest tests/ -v`
4. Ensure code follows PEP 8 with type hints and docstrings.
5. Open a pull request with a clear description.

---

## Service Details

### OBU Simulator

Simulates a vehicle's OBU sending GPS data along a predefined NYC route (lat 40.700→40.720, lon -74.010→-74.000) that passes through **Zone1** (seeded automatically by the Toll Processor on startup).

### Toll Processor

- Consumes GPS data from Kafka
- Maintains vehicle state in Redis (6-hour TTL)
- Detects zone entry/exit using PostGIS `ST_Contains` (spatial GiST index on `toll_zones.geom`)
- Validates GPS timestamps (rejects messages older than 10 min or more than 60 s in the future)
- Calculates toll charges using the Haversine formula
- Publishes toll events to Kafka
- Exposes HTTP health/readiness and Prometheus metrics

### Billing Service

- Consumes toll events from Kafka (`auto_offset_reset=earliest` — no events lost during restarts)
- Creates billing transactions with idempotency (deduplication by `toll_event_id`)
- Processes payments via configurable gateway (mock by default)
- Tracks `retry_count` per transaction; `last_updated` auto-managed by a DB trigger
- REST API with constant-time API key auth, CORS middleware, and `X-Request-ID` tracing header
- Prometheus metrics: transaction counters, payment duration histogram, Kafka consumer throughput
