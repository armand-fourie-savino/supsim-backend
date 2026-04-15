# Backend Architecture

## Overview

SupSim backend is a multi-tenant supply chain analytics and simulation platform. The architecture follows a three-layer design optimized for interactive dashboard queries and what-if simulations over data stored in Apache Iceberg tables.

```
                    ┌──────────────┐
                    │   Cognito    │
                    │  User Pools  │
                    └──────┬───────┘
                           │ JWT
                    ┌──────▼───────┐
                    │  API Gateway │
  Client ──────►   │  (HTTP API)  │
                    │ JWT Authorizer│
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  ECS Fargate │
                    │  ┌─────────┐ │      ┌───────────┐
                    │  │ FastAPI │ │◄────►│ DynamoDB  │
                    │  └────┬────┘ │      │ (app state)│
                    │  ┌────▼────┐ │      └───────────┘
                    │  │ DuckDB  │ │
                    │  │(embedded)│ │
                    │  └────┬────┘ │
                    └───────┼──────┘
                           │
                    ┌──────▼───────┐
                    │  S3 Iceberg  │
                    │  (Glue Cat.) │
                    └──────────────┘
```

## Architecture Layers

### Storage Layer — S3 Iceberg

All analytics data lives in Apache Iceberg tables on S3, registered in the AWS Glue Catalog.

- **Account**: `016146521450`
- **Region**: `af-south-1`
- **Schema**: Star schema, optimized for analytical queries
- **Partitioning**: Tables partitioned by `customer_id` for tenant isolation and query pruning
- **Format**: Parquet files on S3 with Iceberg metadata

Iceberg provides schema evolution, time travel (point-in-time queries), and partition pruning — all critical for supply chain data where product hierarchies change over time.

This layer is managed by the existing data warehouse pipeline and is read-only from the backend's perspective.

### Serving Layer — DuckDB (Embedded)

DuckDB runs embedded inside each ECS Fargate task as the OLAP query engine. It connects to Iceberg tables via the Glue Catalog — no separate ingestion pipeline required.

- **Connection mode**: `READ_ONLY` (or in-memory instances querying S3 externally)
- **Glue integration**: `ATTACH '<account_id>' (TYPE ICEBERG, ENDPOINT_TYPE GLUE)` — validated in `duck-db-test/duck_db_test_glue.py`
- **Extensions**: `iceberg`, `httpfs` (must be installed and loaded)
- **Per-worker isolation**: Each Fargate task runs its own DuckDB instance, no shared state

### Application Layer — FastAPI + API Gateway

FastAPI handles business logic, request validation, and response formatting. API Gateway HTTP API sits in front, providing JWT authorization, rate limiting, and routing.

- **API Gateway**: Native Cognito JWT authorizer, per-tenant usage plans, built-in throttling
- **FastAPI**: Async framework with Pydantic v2 validation and dependency injection
- **Compute**: ECS Fargate tasks running containerized FastAPI + DuckDB

## Multi-Tenancy Strategy

### Approach: Shared Tables, Partitioned by `customer_id`

All tenants share the same Iceberg tables, partitioned by `customer_id`. This provides:
- **Performance**: DuckDB only reads Parquet files for the requested tenant (partition pruning)
- **Simplicity**: No per-tenant DDL, schema migrations, or table management
- **Isolation**: Each query is automatically scoped to one tenant's data

### Tenant Resolution Flow

1. User authenticates via Cognito → receives JWT with `cognito:groups` claim (e.g., `tenant_acme`)
2. API Gateway validates JWT via Cognito JWT authorizer
3. FastAPI reads `cognito:groups` from the API Gateway request context
4. DynamoDB Tenants table maps the group name to `customer_id`:

   | PK (`tenant_group`) | `customer_id` | `display_name` | `plan_tier` | `feature_flags` |
   |---|---|---|---|---|
   | `tenant_acme` | `ACME001` | Acme Corp | `pro` | `{"simulations": true}` |

5. `TenantContext` (frozen dataclass) is constructed and injected into all downstream services
6. `query_builder.py` ensures every DuckDB query includes `WHERE customer_id = :customer_id`

The DynamoDB lookup is cached in-process since tenant config changes infrequently.

### Noisy Neighbor Protection

- **API Gateway**: Per-tenant usage plans with request throttling
- **Application**: Per-tenant concurrency caps (semaphore per `tenant_id`)
- **DuckDB**: Query timeouts (`SET timeout`) and memory limits (`SET memory_limit`)
- **Worker pools**: Separate pools for dashboard queries vs simulations

## Data Flow

### Dashboard Queries

```
Client → API Gateway (JWT auth) → FastAPI → ThreadPoolExecutor → DuckDB cursor
  → S3/Iceberg (partition-pruned by customer_id) → response
```

1. API Gateway validates the JWT and forwards the request with user claims
2. FastAPI middleware extracts `tenant_group` from claims, resolves `customer_id` via DynamoDB (cached)
3. Service layer calls `query_builder` which constructs a tenant-scoped SQL query
4. Query is executed on a `ThreadPoolExecutor` thread (DuckDB is CPU-bound, not async)
5. DuckDB reads only the relevant Parquet partitions from S3
6. Results are serialized via Pydantic and returned

### Simulation (What-If Scenarios)

```
Client → API Gateway → FastAPI → validate config → DynamoDB (persist)
  → simulation worker pool → DuckDB (scenario computation)
  → S3 (results) + DynamoDB (metadata) → client polls for status
```

1. Client submits a simulation config (demand shock, route change, order combination)
2. FastAPI validates the config and persists it to DynamoDB
3. Simulation is submitted to a dedicated background worker pool
4. Worker hydrates the tenant's data slice via DuckDB, applies scenario transformations
5. Results (projected stock levels, stockout dates, coverage metrics) are stored in S3
6. Simulation metadata and status are updated in DynamoDB
7. Client polls for completion or receives status updates

## Caching Strategy

### Phase 1: In-Process Cache

- **Implementation**: `cachetools.TTLCache` (or similar) in each FastAPI worker
- **Cache key**: `hash(tenant_id, query_type, params_hash)`
- **Scope**: Per-Fargate-task (not shared across tasks)
- **Benefit**: Zero additional infrastructure, works well with single-task deployment

### Future: Redis (Phase 2)

When scaling to multiple Fargate tasks, add ElastiCache Redis for shared cache:
- Query result caching across workers
- Per-tenant rate limiting counters
- Simulation job status (if moving to distributed workers)

### Open Decisions

- [ ] **Cache TTLs**: Per query type — dashboard aggregations (5 min?), detail views (30s?), simulation results (no cache?)
- [ ] **Cache invalidation**: When Iceberg snapshots update, how does the cache know? Options: poll Glue catalog metadata periodically, or accept staleness within TTL window
- [ ] **Parquet file caching**: Rely on DuckDB's internal file cache (OS page cache) or explicit pre-loading? Memory budget depends on Fargate task size

## Concurrency Model

### DuckDB in Multi-Worker API

DuckDB's concurrency model: single-writer, multiple-reader. Since the backend only reads Iceberg data (never writes to DuckDB), this constraint is irrelevant.

- **Per-worker DuckDB instance**: Each Fargate task creates one DuckDB connection at startup
- **Per-request cursor**: `con.cursor()` creates a lightweight cursor for each request — cheap and thread-safe
- **Cooperative scans**: DuckDB's internal scheduler shares I/O across concurrent cursors, so two queries on the same partition don't double the S3 reads
- **ThreadPoolExecutor**: DuckDB queries are CPU-bound; they run on a thread pool to avoid blocking FastAPI's async event loop

### Worker Pool Separation

Two named `ThreadPoolExecutor` instances:

1. **Dashboard pool** — Sized for low-latency concurrent dashboard queries. Higher thread count, strict timeout.
2. **Simulation pool** — Sized for fewer, longer-running simulation computations. Lower thread count, relaxed timeout.

This prevents a heavy simulation from blocking dashboard requests.

### Horizontal Scaling

- Add Fargate tasks to scale out — each task is fully independent
- No shared DuckDB state means linear scaling
- Consider consistent routing by `tenant_id` for cache locality when running multiple tasks

### Open Decisions

- [ ] **Timeout values**: Dashboard queries (30s?), simulations (300s?)
- [ ] **Memory limits**: `SET memory_limit` per DuckDB instance — depends on Fargate task memory allocation (512MB of 1GB?)
- [ ] **ThreadPoolExecutor sizing**: Threads per pool per vCPU
- [ ] **Simulation durability**: In-process `ThreadPoolExecutor` loses running simulations on task restart. Acceptable for v1, or add SQS for durability?
- [ ] **Consistent routing**: API Gateway doesn't support sticky sessions. With single task initially this is moot. At scale, options include NLB layer or accept cache misses.

## Security Model

### Authentication

- **Cognito User Pools**: Manages user registration, login, MFA, password policies
- **Cognito Groups**: One group per tenant (e.g., `tenant_acme`), users assigned to their tenant's group
- **JWT tokens**: Issued by Cognito, include `cognito:groups` claim
- **API Gateway JWT Authorizer**: Validates token signature and expiry before requests reach FastAPI

### Authorization

- Tenant isolation enforced at multiple layers:
  1. **API Gateway**: JWT must be valid
  2. **FastAPI middleware**: Extracts `tenant_group`, resolves `customer_id`
  3. **Query builder**: Injects `WHERE customer_id = :customer_id` into every DuckDB query
  4. **DuckDB READ_ONLY mode**: Cannot modify data even if query builder is bypassed

### Network Security

- HTTPS termination at API Gateway
- ECS tasks in private subnets (no public IP)
- Security groups: only API Gateway → ECS on application port
- IAM roles: ECS task role scoped to S3 read, DynamoDB read/write, Secrets Manager read

### Open Decisions

- [ ] **CORS**: Allowed origins per environment
- [ ] **Security headers**: HSTS, CSP, X-Content-Type-Options (API Gateway response headers or FastAPI middleware)
