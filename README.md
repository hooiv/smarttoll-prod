# SmartToll - Toll Processing System

A modern, scalable microservices architecture for processing GPS data from vehicles, calculating toll charges, and handling billing.

## System Overview

SmartToll consists of three main components:

1. **OBU Simulator**: Generates simulated GPS data from vehicles and publishes it to Kafka.
2. **Toll Processor**: Processes real-time GPS data, detects when vehicles enter/exit toll zones, and calculates toll charges.
3. **Billing Service**: Handles toll event processing, payment processing, and provides a REST API for transaction status.

## Tech Stack

- **Messaging**: Apache Kafka
- **Cache**: Redis
- **Database**: PostgreSQL with PostGIS extension
- **API**: FastAPI (Billing Service)
- **Container Orchestration**: Docker Compose

## Prerequisites

- Python 3.9+ installed
- Docker & Docker Compose (v1.29+)
- Access to Kafka, Zookeeper, Redis, and Postgres (local via Compose or remote)

## Environment Variables

Create `.env` files in each service directory (`billing_service/` and `toll_processor/`) with:

```
# Common settings
BIND_HOST=0.0.0.0
BIND_PORT=8001
LOG_LEVEL=INFO

# Kafka
KAFKA_BOOTSTRAP_SERVERS=localhost:9093
TOLL_EVENT_TOPIC=smarttoll.toll.events.v1
GPS_TOPIC=smarttoll.gps.raw.v1
PAYMENT_TOPIC=smarttoll.payment.events.v1

# Postgres
DB_HOST=localhost
DB_PORT=5433
DB_NAME=test_smarttoll
DB_USER=test_user
DB_PASSWORD=test_password

# Redis
REDIS_HOST=localhost
REDIS_PORT=6380

# API Auth (billing_service only)
SERVICE_API_KEY=supersecretapikey123
```

## Getting Started

### Running Locally (Development)

1. In one terminal, start infrastructure:
   ```bash
   docker-compose -f tests/integration/docker-compose.integration.yml up -d
   ```
2. Install Python dependencies:
   ```bash
   cd billing_service
   pip install -r requirements.txt -r requirements-dev.txt
   cd ../toll_processor
   pip install -r requirements.txt -r requirements-dev.txt
   ```
3. Start services:
   - Billing Service:
     ```bash
     cd billing_service
     uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
     ```
   - Toll Processor:
     ```bash
     cd toll_processor
     python -m app.main
     ```
4. Verify health and metrics:
   - Toll Processor liveness: `http://localhost:8080/health/live`
   - Toll Processor readiness: `http://localhost:8080/health/ready`
   - Toll Processor metrics: `http://localhost:8081/`
   - Billing Service liveness: `http://localhost:8001/api/v1/health/live`
   - Billing Service readiness: `http://localhost:8001/api/v1/health/ready`

### Running Integration Tests

From the project root:
```bash
pip install -r requirements-dev.txt
pytest
```
Pytest will spin up the test Compose stack automatically via `pytest.ini` and `pytest-docker`.

### Docker Compose (Production)

A top-level `docker-compose.yml` is provided. To build and run:

```bash
docker-compose build billing_service toll_processor
docker-compose up -d
```

Services will be available on ports 8001 (billing) and 8080/8081 (toll processor).

### Deploying to Production

1. Push images to your container registry:
   ```bash
   docker tag billing_service my-registry/billing_service:latest
   docker push my-registry/billing_service:latest
   docker tag toll_processor my-registry/toll_processor:latest
   docker push my-registry/toll_processor:latest
   ```
2. Provision infrastructure (Kubernetes/ECS/VM + Compose) with external Kafka/Redis/Postgres instances.
3. Apply your orchestration manifests or Helm charts; configure liveness/readiness probes on the HTTP endpoints and Prometheus scraping on `/metrics`.
4. Monitor logs and metrics via Prometheus/Grafana.

## Service Details

### OBU Simulator

Simulates a vehicle's On-Board Unit sending GPS data along a predefined route. The simulator sends data to Kafka and can be configured via environment variables.

### Toll Processor

Stateless service that:
- Consumes GPS data from Kafka
- Maintains vehicle state in Redis
- Detects toll zone entry/exit using PostGIS
- Calculates toll charges based on distance traveled
- Publishes toll events to Kafka

### Billing Service

REST API service that:
- Consumes toll events from Kafka
- Processes payments via a payment gateway
- Stores transaction records in PostgreSQL
- Provides API endpoints for querying transaction status

## Configuration

Environment variables can be set in the `.env` file or passed directly to Docker Compose.

