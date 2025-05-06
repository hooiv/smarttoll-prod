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

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Git

### Running the System

1. Clone this repository:
```bash
git clone https://github.com/yourusername/smarttoll-prod-blueprint.git
cd smarttoll-prod-blueprint
```

2. Start the services:
```bash
docker-compose up -d
```

3. Monitor the logs:
```bash
docker-compose logs -f
```

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

