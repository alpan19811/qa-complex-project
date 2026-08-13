# QA Automation Training Stand (Python + Pytest)

A hands-on integration testing stand for practicing and demonstrating
QA Automation skills: REST API testing, database verification, mock services,
message brokers, caching and containerized test execution.

## Tech Stack

- **Python 3.12+ / Pytest** — fixtures, parametrization, pytest-xdist, pytest-asyncio
- **FastAPI** — application under test (CRUD REST API)
- **PostgreSQL 16** — relational DB for integration scenarios
- **Redis 7** — caching (cache-aside pattern, TTL, invalidation)
- **NATS** — message broker (Pub/Sub, Queue Groups, async scenarios)
- **WireMock** — mock server (stubs, 5xx simulation, latency)
- **Docker / Docker Compose** — infrastructure and containerized test runs
- **Locust** — load testing (RPS, percentiles analysis)

## Project Structure

Complex_Project/
├── tests/ # Pytest test suites
│ ├── test_api.py # REST API CRUD tests (200/201/204/400/404/409/422)
│ ├── test_api_advanced.py# parametrization + fixture scopes
│ ├── test_postgres.py # DB integration tests, transaction rollback isolation
│ ├── test_wiremock.py # mock scenarios (success, 502, latency)
│ ├── test_nats.py # Pub/Sub, Queue Groups, eventual consistency
│ └── test_redis.py # cache-aside, TTL, invalidation
├── wiremock_data/mappings/ # WireMock stub definitions (JSON)
├── main.py # FastAPI service under test
├── locustfile.py # load testing scenarios
├── docker-compose.yml # postgres + redis + nats + wiremock
├── Dockerfile # containerized test runner
└── requirements.txt



## Quick Start

**1. Start the infrastructure:**

```bash
docker compose up -d


2. Run the application under test:
uvicorn main:app --port 8000

3. Run tests locally:
pytest tests/ -v

4. Run tests in Docker (as in CI):
docker build -t my-qa-tests:latest .
docker run --rm my-qa-tests:latest


Load Testing
locust -f locustfile.py --headless -u 100 -r 10 -t 30s --host http://localhost:8000