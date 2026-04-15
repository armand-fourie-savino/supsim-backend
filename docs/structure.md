# Project Structure

## Directory Layout

```
supsim-backend/
├── docs/
│   ├── architecture.md          # System architecture and data flow
│   ├── tech.md                  # Technology choices and justifications
│   └── structure.md             # This file — project organization
├── src/
│   └── supsim/
│       ├── __init__.py
│       ├── main.py              # FastAPI app factory, lifespan events
│       ├── config.py            # Settings via pydantic-settings
│       ├── dependencies.py      # Shared FastAPI dependencies
│       │
│       ├── api/
│       │   ├── v1/
│       │   │   ├── router.py    # Aggregates all v1 endpoint routers
│       │   │   └── endpoints/
│       │   │       ├── health.py        # GET /health, GET /ready
│       │   │       ├── analytics.py     # Stock levels, burn rates, incoming
│       │   │       ├── simulations.py   # CRUD + run/status for simulations
│       │   │       └── tenants.py       # Tenant config (admin)
│       │   └── middleware/
│       │       ├── tenant_context.py    # Extract tenant from API GW claims
│       │       ├── error_handler.py     # Global exception → HTTP response
│       │       └── logging.py          # Request/response structured logging
│       │
│       ├── core/
│       │   ├── tenant.py        # TenantContext frozen dataclass
│       │   ├── exceptions.py    # Custom exception hierarchy
│       │   └── pagination.py    # Pagination models and utilities
│       │
│       ├── models/
│       │   ├── schemas/         # Pydantic request/response models
│       │   │   ├── analytics.py     # StockLevel, BurnRate, IncomingStock
│       │   │   ├── simulations.py   # SimulationConfig, SimulationResult
│       │   │   └── common.py        # PaginatedResponse, ErrorResponse
│       │   └── domain/          # Internal domain models
│       │       ├── tenant.py
│       │       └── simulation.py
│       │
│       ├── services/
│       │   ├── analytics_service.py     # Query orchestration + caching
│       │   ├── simulation_service.py    # Simulation lifecycle management
│       │   └── tenant_service.py        # Tenant config CRUD
│       │
│       ├── db/
│       │   ├── duckdb/
│       │   │   ├── connection.py        # DuckDB lifecycle, Glue attach
│       │   │   ├── query_builder.py     # Tenant-scoped query construction
│       │   │   └── queries/
│       │   │       ├── stock.py         # Stock level queries
│       │   │       ├── burn_rate.py     # Burn rate / demand forecast queries
│       │   │       ├── incoming.py      # Incoming stock/order queries
│       │   │       └── simulation.py    # Simulation data hydration queries
│       │   └── dynamodb/
│       │       ├── client.py            # boto3 DynamoDB client wrapper
│       │       └── repositories/
│       │           ├── tenant_repo.py       # Tenant table operations
│       │           ├── simulation_repo.py   # Simulation metadata CRUD
│       │           └── audit_repo.py        # Audit log writes (with TTL)
│       │
│       ├── workers/
│       │   ├── pool.py                  # ThreadPoolExecutor management
│       │   └── simulation_worker.py     # Background simulation job runner
│       │
│       └── cache/
│           ├── manager.py               # TTLCache get/set/invalidate
│           └── keys.py                  # Deterministic cache key generation
│
├── tests/
│   ├── conftest.py              # Shared fixtures, test client, mock data
│   ├── unit/
│   │   ├── test_analytics_service.py
│   │   ├── test_simulation_service.py
│   │   ├── test_tenant_context.py
│   │   └── test_query_builder.py
│   └── integration/
│       ├── test_analytics_endpoints.py
│       ├── test_simulation_endpoints.py
│       └── test_duckdb_connection.py
│
├── Dockerfile
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .dockerignore
└── .gitignore
```

## Module Responsibilities

### `main.py` — Application Entry Point

FastAPI app factory with lifespan context manager:
- **Startup**: Initialize DuckDB connection (install extensions, attach Glue catalog, create AWS secrets), initialize DynamoDB client, create thread pools
- **Shutdown**: Close DuckDB connection, shutdown thread pools
- **Registration**: Mount v1 router, add middleware (tenant context, error handler, logging)

### `config.py` — Configuration

`pydantic-settings` `BaseSettings` class loading from environment variables:
- AWS configuration (region, account ID, Glue catalog)
- DuckDB settings (memory limit, timeout, thread pool sizes)
- DynamoDB table names
- Cognito settings (user pool ID, app client ID)
- Cache TTLs
- Log level

### `dependencies.py` — Shared FastAPI Dependencies

Reusable `Depends()` callables:
- `get_tenant_context()` — resolves Cognito groups from API Gateway claims, looks up `customer_id` from DynamoDB (cached), returns `TenantContext`
- `get_duckdb_cursor()` — yields a DuckDB cursor from the worker's connection
- `get_dynamodb_client()` — returns the shared DynamoDB client

### `api/v1/endpoints/` — Route Handlers

Thin layer: validate input via Pydantic, call service, return response. No business logic here.

- `health.py` — `GET /health` (liveness), `GET /ready` (readiness — checks DuckDB + DynamoDB)
- `analytics.py` — Stock levels, burn rates, incoming stock. Accepts filters (SKU, analytical unit, time range)
- `simulations.py` — Create simulation config, run simulation, get status, list results
- `tenants.py` — Tenant configuration (admin endpoints, feature flags)

All endpoints receive `TenantContext` via dependency injection. The `tenant_id` is never accepted from query parameters or request body.

### `api/middleware/tenant_context.py` — Tenant Resolution

Extracts tenant identity from the API Gateway request context:
1. Reads `cognito:groups` from the request (injected by API Gateway after JWT validation)
2. Looks up the group in DynamoDB Tenants table to get `customer_id`
3. Constructs a `TenantContext` frozen dataclass
4. Attaches to `request.state` for downstream access

### `api/middleware/error_handler.py` — Exception Handling

Global exception handler mapping custom exceptions to HTTP responses:
- `TenantNotFoundError` → 404
- `QueryTimeoutError` → 504
- `ConcurrencyLimitError` → 429
- `ValidationError` → 422
- Unhandled exceptions → 500 with structured error response (no stack traces in production)

### `core/` — Cross-Cutting Concerns

- `tenant.py` — `TenantContext` frozen dataclass: `tenant_id`, `customer_id`, `plan_tier`, `feature_flags`
- `exceptions.py` — Custom exception hierarchy rooted at `SupSimError`
- `pagination.py` — Cursor-based or offset pagination models

### `models/schemas/` — Pydantic Models

Request/response models for the API. These define the contract with the frontend:
- `analytics.py` — `StockLevelResponse`, `BurnRateResponse`, `IncomingStockResponse`, filter models
- `simulations.py` — `SimulationConfigRequest`, `SimulationResultResponse`, `SimulationStatusResponse`
- `common.py` — `PaginatedResponse[T]`, `ErrorResponse`

### `models/domain/` — Domain Models

Internal frozen dataclasses representing business entities. Not exposed via the API:
- `tenant.py` — `Tenant` with config and feature flags
- `simulation.py` — `SimulationConfig`, `SimulationResult`, scenario parameter types

### `services/` — Business Logic

Services own all business logic. They depend on repositories (db layer) and never import FastAPI request objects.

- `analytics_service.py` — Orchestrates DuckDB queries for dashboard data. Checks cache first, queries DuckDB on miss, caches result. Applies tenant scoping via `query_builder`.
- `simulation_service.py` — Validates simulation configs, persists to DynamoDB, submits to worker pool, tracks status. Stores large results in S3, metadata in DynamoDB.
- `tenant_service.py` — Tenant configuration CRUD. Reads/writes to DynamoDB Tenants table.

### `db/duckdb/connection.py` — DuckDB Lifecycle

Manages the DuckDB connection for a Fargate task:
1. Create connection (`duckdb.connect()` in READ_ONLY or in-memory mode)
2. Install and load extensions (`iceberg`, `httpfs`)
3. Create AWS secret with IAM credentials
4. Attach Glue Catalog (`ATTACH '<account_id>' (TYPE ICEBERG, ENDPOINT_TYPE GLUE)`)

Pattern established in `duck-db-test/duck_db_test_glue.py`.

### `db/duckdb/query_builder.py` — Tenant-Scoped Queries

Defense-in-depth for multi-tenancy. Every query passes through the builder which:
- Injects `WHERE customer_id = ?` with parameterized `customer_id`
- Applies pagination (LIMIT/OFFSET or cursor)
- Adds time range filters
- Never allows raw SQL from application code

### `db/duckdb/queries/` — SQL Query Definitions

Each module contains parameterized SQL strings for its domain:
- `stock.py` — Current stock levels, historical stock by period
- `burn_rate.py` — Demand forecasts, current burn rates
- `incoming.py` — In-transit orders, expected arrival dates
- `simulation.py` — Data hydration queries for simulation scenarios

### `db/dynamodb/` — DynamoDB Access

- `client.py` — Thin wrapper around `boto3.resource('dynamodb')`. Handles table references, serialization/deserialization.
- `repositories/` — Data access per aggregate:
  - `tenant_repo.py` — Get/put tenant config by group name
  - `simulation_repo.py` — CRUD for simulation metadata, list by tenant
  - `audit_repo.py` — Write audit entries with TTL for automatic expiration

### `workers/` — Background Processing

- `pool.py` — Two named `ThreadPoolExecutor` instances:
  - `dashboard_pool` — Higher concurrency, strict timeout (dashboard queries)
  - `simulation_pool` — Lower concurrency, relaxed timeout (simulations)
- `simulation_worker.py` — Receives simulation config, hydrates tenant data via DuckDB, applies scenario transformations, writes results to S3 and metadata to DynamoDB

### `cache/` — In-Process Caching

- `manager.py` — Wraps `cachetools.TTLCache`. Provides typed `get()`, `set()`, `invalidate()` methods. Thread-safe.
- `keys.py` — Generates deterministic cache keys from `(tenant_id, query_type, params_hash)`. Ensures different tenants never share cache entries.

## Key Design Patterns

### Dependency Injection

FastAPI `Depends()` chains for clean composition:
```python
@router.get("/stock-levels")
async def get_stock_levels(
    tenant: TenantContext = Depends(get_tenant_context),
    service: AnalyticsService = Depends(get_analytics_service),
):
    return await service.get_stock_levels(tenant)
```

### Repository Pattern

DynamoDB access is isolated behind repository classes. Services never construct DynamoDB queries directly:
```python
class TenantRepository(Protocol):
    def get_by_group(self, group_name: str) -> Tenant | None: ...
    def save(self, tenant: Tenant) -> Tenant: ...
```

### Frozen Dataclasses

Domain models are immutable:
```python
@dataclass(frozen=True)
class TenantContext:
    tenant_id: str
    customer_id: str
    plan_tier: str
    feature_flags: dict[str, bool]
```

### Service Layer Isolation

- **Endpoints**: Validate input, call service, return response
- **Services**: Business logic, orchestration, caching decisions
- **Repositories**: Data access only, no business rules
- **Query builder**: SQL construction and tenant scoping

No layer reaches past its immediate dependency.

## Docker Configuration

Multi-stage `Dockerfile`:
1. **Build stage**: Install Python dependencies
2. **Runtime stage**: Slim Python image with only runtime deps

Key considerations:
- Pre-install DuckDB extensions (`iceberg`, `httpfs`) during build to avoid runtime downloads
- Run as non-root user
- Health check: `CMD ["curl", "-f", "http://localhost:8000/health"]`

## Open Decisions

- [ ] **DynamoDB table design**: Single-table (PK/SK overloading) vs. multi-table (one per entity)
- [ ] **Testing strategy**: `moto` for DynamoDB mocking? Test Iceberg dataset for integration tests? LocalStack?
- [ ] **DuckDB extension pre-install**: Set `DUCKDB_EXTENSION_DIRECTORY` and download in `Dockerfile`
- [ ] **CI/CD pipeline**: GitHub Actions workflow structure, environment promotion, Docker layer caching
