# Netzence Sustainability - Carbon Credits Microservice

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7-DC382D.svg?logo=redis&logoColor=white)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)

A production-grade, asynchronous backend service built for **Netzence Sustainability Limited** that awards carbon credits for completed rides in Electric Vehicles (EV), tracks 12-month credit expirations, consumes credits via **FIFO**, enforces concurrency safety during redemption, maintains an immutable double-entry audit ledger, and supports ride cancellations.

Orchestrated using **Docker Compose** with **FastAPI**, **PostgreSQL 16**, and **Redis 7**.

---

## 🌟 Core Requirements & Domain Architecture

1. **Carbon Credits Issuance (`POST /rides/completed`)**:
   - Calculates carbon credits with 4 decimal places (`NUMERIC(12, 4)`): $1.0\text{ credit/km}$ for Electric Vehicles (EV), eliminating floating-point rounding errors.
   - **Idempotency Guarantee**: Redelivery of the same `ride_id` is safely ignored without duplicate credit awards or ledger entries.
2. **12-Month Expiration & FIFO Redemption (`POST /drivers/{id}/redeem`)**:
   - Credits expire **12 months** after the ride's `completed_at`.
   - Redemptions consume the **oldest unexpired credits first (FIFO)**.
   - Balance calculations strictly ignore expired credits.
3. **Concurrency-Safe Redemption**:
   - Dedicated row-level lock (`SELECT ... FOR UPDATE` on `driver_locks`) strictly prevents simultaneous redemption race conditions.
   - **Two concurrent redeem requests can never drive the balance below zero**.
4. **Audit Ledger & Cancellations (`POST /rides/cancelled`)**:
   - Reversing a cancelled ride marks the credit lot as `REVERSED` and writes an immutable `REVERSAL` ledger entry.
   - The driver's history (`GET /drivers/{id}/history`) preserves the full audit trail: original `CREDIT`, any `DEBIT`s, and `REVERSAL`s.
   - Handles **out-of-order cancellations** arriving prior to completions via cancellation tombstones (0 credits awarded upon delayed completion).
5. **Architectural Decisions**:
   - See [DECISIONS.md](file:///Users/taiwokazeem/Documents/practice/python/fastapi/netzence-test/DECISIONS.md) for detailed trade-off analyses, data model decisions, and crash-recovery guarantees.

---

## 🏗️ Architecture & Project Structure

```text
├── .env.example                     # Environment variables template
├── .env                             # Active environment configuration
├── .gitignore                       # Git ignore rules
├── .dockerignore                    # Docker build ignore rules
├── Dockerfile                       # Multi-stage production container definition
├── docker-compose.yml               # Service orchestration (web, db, redis)
├── docker-compose.override.yml.example # Template for live-reload development
├── Makefile                         # Convenient workflow shortcuts
├── pyproject.toml                   # Project metadata, pytest, and linter configs
├── requirements.txt                 # Production dependencies
├── requirements-dev.txt             # Testing and development dependencies
├── alembic.ini                      # Database migration settings
├── scripts/
│   ├── entrypoint.sh                # Container entrypoint with auto-migration
│   └── wait_for_services.py         # Asynchronous health poller for Postgres & Redis
├── alembic/
│   ├── env.py                       # Async Alembic execution environment
│   └── versions/
│       └── 0001_initial_schema.py   # Baseline schema for items table
├── app/
│   ├── main.py                      # FastAPI app initialization, lifespan & middleware
│   ├── core/
│   │   ├── config.py                # Pydantic v2 BaseSettings configuration
│   │   ├── database.py              # Async SQLAlchemy engine & session dependency
│   │   ├── redis.py                 # Redis connection pool & cache helpers
│   │   ├── logging.py               # Structured JSON & Request ID logging
│   │   └── exceptions.py            # Custom exceptions & global handlers
│   ├── models/
│   │   ├── base.py                  # SQLAlchemy DeclarativeBase & Timestamp mixin
│   │   └── item.py                  # Item database entity
│   ├── schemas/
│   │   ├── health.py                # Healthcheck response schemas
│   │   └── item.py                  # Pydantic validation & response schemas
│   ├── repositories/
│   │   └── item_repository.py       # Data access layer for items
│   ├── services/
│   │   └── item_service.py          # Business logic & Redis caching layer
│   └── api/
│       ├── deps.py                  # Dependency injection utilities
│       └── v1/
│           ├── api.py               # v1 Router aggregator
│           └── endpoints/
│               ├── health.py        # /health, /health/live, /health/ready
│               └── items.py         # RESTful CRUD operations
└── tests/
    ├── conftest.py                  # AsyncClient fixtures
    ├── test_health.py               # Health probe unit tests
    └── test_items.py                # Items API integration tests
```

---

## 🚀 Quickstart with Docker Compose

### 1. Start the entire application
Clone the repository and run:
```bash
docker compose up -d --build
```

This starts:
1. **PostgreSQL** (`fastapi_postgres` on port `5432`)
2. **Redis** (`fastapi_redis` on port `6379`)
3. **FastAPI Web Service** (`fastapi_web` on port `8000`)
   - Waits for Postgres and Redis to pass internal health checks.
   - Runs `alembic upgrade head` to apply any pending database migrations.
   - Launches `uvicorn` with production workers.

### 2. Verify Application Health
Check overall service status:
```bash
curl http://localhost:8000/api/v1/health
```
Response:
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "0.1.0",
  "services": {
    "database": {
      "status": "up",
      "latency_ms": 1.25,
      "error": null
    },
    "redis": {
      "status": "up",
      "latency_ms": 0.84,
      "error": null
    }
  },
  "timestamp": "2026-11-03T10:15:30.123456"
}
```

### 3. Explore Interactive API Docs
Open your browser to:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### 4. Stop the entire application
To gracefully shut down all services:
```bash
docker compose down
```
*Or:*
```bash
make down
```

To stop and remove persistent volumes (clears database and cache):
```bash
docker compose down -v
# or
make down-v
```

---

## 🛠️ Carbon Credits REST API Usage Examples

### 1. Record Completed Ride (`POST /rides/completed`)
```bash
curl -X POST http://localhost:8000/rides/completed \
  -H "Content-Type: application/json" \
  -d '{
    "ride_id": "ride_101",
    "driver_id": "driver_abc",
    "distance_km": 15.5,
    "vehicle_type": "EV",
    "completed_at": "2026-11-03T12:00:00Z"
  }'
```

### 2. Check Driver Unexpired Balance (`GET /drivers/{id}/balance`)
*Only unexpired credits (< 12 months) are included.*
```bash
curl http://localhost:8000/drivers/driver_abc/balance
```

### 3. Redeem Credits (FIFO) (`POST /drivers/{id}/redeem`)
*Consumes oldest credit lots first. Guaranteed zero-overdraw concurrency safety.*
```bash
curl -X POST http://localhost:8000/drivers/driver_abc/redeem \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 10.0,
    "reason": "Fast charging voucher"
  }'
```

### 4. View Audit Ledger History (`GET /drivers/{id}/history`)
*Returns every CREDIT, DEBIT, and REVERSAL with reasons.*
```bash
curl http://localhost:8000/drivers/driver_abc/history
```

### 5. Cancel Ride (`POST /rides/cancelled`)
*Reverses credits while preserving original credit in audit ledger.*
```bash
curl -X POST http://localhost:8000/rides/cancelled \
  -H "Content-Type: application/json" \
  -d '{
    "ride_id": "ride_101",
    "reason": "Passenger cancelled"
  }'
```

---

## 🗄️ Database Migrations (Alembic)

Migrations are run automatically on container startup. To execute or manage migrations manually:

- **Apply migrations**:
  ```bash
  make migrate
  # or
  docker compose exec web alembic upgrade head
  ```
- **Generate new migration revision**:
  ```bash
  make makemigrations m="add_user_table"
  # or
  docker compose exec web alembic revision --autogenerate -m "add_user_table"
  ```
- **Rollback last migration**:
  ```bash
  docker compose exec web alembic downgrade -1
  ```

---

## 💻 Development with Hot Reload

To edit code locally and have changes reflect immediately without rebuilding Docker images:

1. Copy the override example:
   ```bash
   cp docker-compose.override.yml.example docker-compose.override.yml
   ```
2. Start containers:
   ```bash
   docker compose up
   ```
   Docker Compose will mount your local directory into `/app` and start `uvicorn` with `--reload`.

---

## 🧪 Testing

Run the test suite with pytest inside the container:
```bash
make test
# or
docker compose exec web pytest -v
```

---
