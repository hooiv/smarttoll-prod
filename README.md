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

## Configuration for Docker Compose

SmartToll uses a top-level `.env` file to supply environment variables to all services (Postgres, Redis, Kafka, etc.) when running with Docker Compose. Follow these steps:

1. Create a `.env` file in the project root by copying the template:
   ```bash
   cp .env.example .env
   ```

2. Fill in the required variables in `.env`:
   ```ini
   # Postgres (used by both toll_processor and billing_service)
   POSTGRES_DB=smarttoll_dev
   POSTGRES_USER=smarttoll_user
   POSTGRES_PASSWORD=changeme_in_prod_123!

   # Redis (used by toll_processor)
   REDIS_HOST=redis
   REDIS_PORT=6379
   REDIS_DB=0

   # Kafka (used by all services)
   KAFKA_BROKER=kafka:29092
   GPS_TOPIC=smarttoll.gps.raw.v1
   TOLL_EVENT_TOPIC=smarttoll.toll.events.v1
   PAYMENT_EVENT_TOPIC=smarttoll.payment.events.v1
   CONSUMER_GROUP_ID=toll_processor_group_dev_1
   BILLING_CONSUMER_GROUP_ID=billing_service_group_dev_1

   # Billing Service binding
   BIND_HOST=0.0.0.0
   BIND_PORT=8000

   # API authentication
   SERVICE_API_KEY=supersecretapikey123
   ```

3. (Optional) You can also place service-specific overrides in `billing_service/.env` or `toll_processor/.env`, but the root `.env` is sufficient for Compose.

4. Run Docker Compose as usual:
   ```bash
   docker-compose up -d
   ```

With these settings, Docker Compose will inject all variables into every container that references them.

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

### Deploying for Free

SmartToll can run at zero cost by combining Fly.io’s free tier with free managed data services:

1. Install and authenticate Fly.io CLI:
   ```bash
   # macOS (Homebrew) or Windows (Scoop/winget)
   brew install superfly/tap/flyctl  # or `winget install Fly.io.Flyctl`
   flyctl auth signup                # register an account
   flyctl auth login                 # login interactively
   ```

2. Provision managed data services:
   - PostgreSQL: ElephantSQL “Tiny Turtle” plan (free) → copy your `DATABASE_URL`.
   - Redis: Redis Enterprise Cloud “Essentials” (free) → copy your `REDIS_URL`.
   - Kafka: CloudKarafka “Trial” cluster (free) → copy your `KAFKA_BROKER` URL.

3. Configure secrets on Fly:
   ```bash
   flyctl secrets set \
     DATABASE_URL="<your_postgres_url>" \
     REDIS_URL="<your_redis_url>" \
     KAFKA_BROKER="<your_kafka_url>" \
     POSTGRES_PASSWORD="<db_password>" \
     # any other SERVICE_API_KEY or custom vars
   ```

4. Launch and deploy services:

   # Billing Service
   ```bash
   cd billing_service
   flyctl launch \
     --name smarttoll-billing \
     --region ord \
     --dockerfile Dockerfile \
     --no-deploy      # scaffold a new app without immediate deploy
   flyctl deploy     # builds & deploys billing service
   ```

   # Toll Processor
   ```bash
   cd ../toll_processor
   flyctl launch \
     --name smarttoll-processor \
     --region ord \
     --dockerfile Dockerfile \
     --no-deploy
   flyctl deploy     # builds & deploys toll processor
   ```

5. Access your live services:
   - Billing API
   - Processor health

6. (Optional) Add Prometheus metrics and custom domains via `flyctl services create`.

You can also use Railway.app, Render.com or other free-tier hosts—just adjust the steps above to their CLI and secrets/config UI.

---

## Architecture Diagram

Below is a high-level architecture diagram of the SmartToll system:

```
+----------------+      +----------------+      +-------------------+
|  OBU Simulator | ---> |  Kafka Broker  | ---> |   Toll Processor  |
+----------------+      +----------------+      +-------------------+
                                                    |
                                                    v
                                         +-------------------+
                                         |   Redis Cache     |
                                         +-------------------+
                                                    |
                                                    v
                                         +-------------------+
                                         | Postgres+PostGIS  |
                                         +-------------------+
                                                    |
                                                    v
                                         +-------------------+
                                         | Billing Service   |
                                         +-------------------+
```

---

## API Documentation

The Billing Service exposes a REST API documented with OpenAPI/Swagger. Once the service is running, you can access the interactive API docs at:

- Swagger UI: [http://localhost:8001/docs](http://localhost:8001/docs)
- ReDoc: [http://localhost:8001/redoc](http://localhost:8001/redoc)

### Example Endpoints
- `GET /api/v1/health/live` — Liveness probe
- `GET /api/v1/health/ready` — Readiness probe
- `GET /api/v1/transactions/status/{toll_event_id}` — Get billing transaction status

The API is protected by an API key (see `SERVICE_API_KEY` in your environment variables). Pass it in the `X-API-KEY` header.

---

## Contributing

Contributions are welcome! To get started:

1. Fork the repository and clone your fork.
2. Create a new branch for your feature or bugfix.
3. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
4. Run tests locally before submitting a PR:
   ```bash
   pytest
   ```
5. Ensure your code follows PEP8 and includes docstrings and type hints where appropriate.
6. Open a pull request with a clear description of your changes.

---

## Contact & Support

For questions, issues, or feature requests, please open an issue on GitHub or contact the maintainer.

---

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

