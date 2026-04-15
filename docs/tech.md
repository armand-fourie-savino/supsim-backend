# Technology Choices

## Stack Overview

| Component | Technology | Purpose |
|---|---|---|
| API Framework | FastAPI | Request handling, validation, OpenAPI docs |
| API Gateway | AWS API Gateway HTTP API | JWT auth, rate limiting, routing |
| Authentication | Amazon Cognito | User pools, MFA, JWT issuance |
| OLAP Engine | DuckDB (embedded) | Analytics queries over Iceberg |
| Table Format | Apache Iceberg | Schema evolution, partition pruning, time travel |
| Object Storage | AWS S3 | Iceberg data files (Parquet) |
| Metadata Catalog | AWS Glue | Iceberg table registration |
| App State | Amazon DynamoDB | Tenants, simulations, audit logs |
| Compute | AWS ECS Fargate | Containerized FastAPI + DuckDB |
| Container Registry | AWS ECR | Docker image storage |
| CI/CD | GitHub Actions | Build, test, deploy pipeline |
| Caching | In-process (Phase 1) | Query result caching |
| Secrets | AWS Secrets Manager | Credentials, API keys |
| Logging | Amazon CloudWatch | Structured logs, metrics |
| Package Manager | pip + venv | Dependency management |

## API Gateway HTTP API

### Why API Gateway over ALB

| Concern | API Gateway HTTP API | ALB |
|---|---|---|
| Cost at low traffic | Pay-per-request, $0 idle | ~$16/month minimum |
| Cognito integration | Native JWT authorizer | Requires middleware or ALB auth action |
| Rate limiting | Built-in per-route throttling | Needs WAF or app-level code |
| Per-tenant controls | Usage plans with API keys | Not supported |
| API versioning | Stages (dev/staging/prod) | Path-based routing only |

### Tradeoffs

- **Payload limit**: 10MB max — analytics responses should be well under this
- **Cost crossover**: Per-request pricing exceeds ALB at ~3M+ requests/month
- **No sticky sessions**: Cannot route same tenant to same Fargate task — mitigated by in-process caching per task

## Amazon Cognito

### Why Cognito

- **Managed user pools**: Handles signup, login, password reset, MFA without custom code
- **JWT issuance**: Tokens include `cognito:groups` claim used for tenant resolution
- **API Gateway integration**: Native JWT authorizer — no auth code in FastAPI
- **Groups for multi-tenancy**: One Cognito group per tenant, users assigned at onboarding
- **Cost**: ~$0.0055/MAU, effectively free at low scale

### Tradeoffs

- Less customizable hosted UI than Auth0
- AWS vendor lock-in for identity
- Custom claims require Lambda triggers (but we use groups instead, avoiding this)

## FastAPI

### Why FastAPI

- **Native async**: Important for I/O-bound operations (S3 reads, DynamoDB calls)
- **Automatic OpenAPI docs**: Swagger UI generated from code, speeds frontend integration
- **Pydantic v2**: Fast request/response validation with type safety
- **Dependency injection**: Clean propagation of `TenantContext` through the request lifecycle
- **Type annotations**: Aligns with project coding standards (PEP 8, type hints mandatory)

### Tradeoffs

- CPU-bound DuckDB queries must be offloaded to `ThreadPoolExecutor` (DuckDB is not async)
- Smaller ecosystem than Django for admin panels — but admin is not needed here
- Single-process model means horizontal scaling via multiple Fargate tasks

## DuckDB (Embedded OLAP)

### Why DuckDB

DuckDB runs embedded in the FastAPI process — no separate server, cluster, or ingestion pipeline.

- **Zero infrastructure cost**: The query engine is a Python library, included in Fargate compute
- **Native Iceberg support**: Connects to Iceberg tables via Glue Catalog (`ATTACH` with `TYPE ICEBERG, ENDPOINT_TYPE GLUE`)
- **Native Parquet support**: Also supports direct `read_parquet()` from S3
- **Sub-second latency at <50GB/tenant**: Vectorized columnar execution with partition pruning
- **Already validated**: `duck-db-test/duck_db_test_glue.py` and `duck-db-test/duck_db_test_s3.py` prove connectivity to existing S3 data
- **Dual-use**: Same engine handles both dashboard queries and simulation computations

### DuckDB vs ClickHouse

| Factor | DuckDB | ClickHouse |
|---|---|---|
| Infrastructure | None (embedded library) | Dedicated cluster ($200+/month min) |
| Concurrency | Good at <50 QPS via cursor-per-request | Excellent at 100+ QPS |
| Iceberg support | Native, direct S3 reads | Native, but requires ingestion sync |
| Ops burden | Zero | Schema management, ingestion pipeline, monitoring |
| Data size sweet spot | <50GB per tenant | Any size |
| Migration path | Standard SQL — can swap to ClickHouse later | — |

**Decision**: At <50GB per tenant and low initial concurrency, DuckDB eliminates an entire infrastructure layer. If concurrency becomes a bottleneck, the migration path to ClickHouse is clean — queries are standard SQL, only the connection layer changes.

### DuckDB vs Athena

| Factor | DuckDB | Athena |
|---|---|---|
| Cost | $0 (embedded) | ~$5/TB scanned |
| Latency | Sub-second (cached Parquet) | 2-5s cold start |
| Concurrency | Scales with Fargate tasks | Limited by service quotas |
| Caching | In-process, instant | None (each query scans S3) |

**Decision**: Athena is the wrong tool for customer-facing dashboard traffic — too slow and too expensive at high QPS.

### Concurrency Model

DuckDB operates in two modes: read-write (single writer) and read-only (multiple readers). Since the backend never writes to DuckDB, the single-writer constraint is irrelevant.

- **Per-worker instance**: Each Fargate task creates one DuckDB connection at startup
- **Per-request cursor**: `con.cursor()` is lightweight and thread-safe within one connection
- **Cooperative scans**: Multiple cursors share I/O when hitting the same Parquet files
- **Horizontal scaling**: Add Fargate tasks for more DuckDB instances — no shared state

## DynamoDB (All App State)

### Why DynamoDB over Postgres

- **Fully serverless**: Pay-per-request pricing, scales to zero cost with no traffic
- **No fixed costs**: vs. RDS minimum ~$12/month even idle
- **Single-digit ms latency**: Fast for key-value lookups (tenant config, user profiles)
- **TTL support**: Automatic expiration for audit logs and temporary data
- **Managed backups**: Point-in-time recovery built-in

### What Lives in DynamoDB

| Data | Access Pattern | Key Design |
|---|---|---|
| Tenant config | Lookup by group name | PK: `tenant_group` |
| User-tenant mappings | Lookup by user ID | PK: `user_id` |
| Simulation metadata | List by tenant, get by ID | PK: `tenant_id`, SK: `simulation_id` |
| Audit logs | Query by tenant + time range | PK: `tenant_id`, SK: timestamp (with TTL) |
| Saved views / dashboards | List by tenant | PK: `tenant_id`, SK: `view_id` |

Simulation result data (large datasets) is stored in S3 with DynamoDB holding metadata pointers.

### Tradeoffs

- No relational joins — complex queries across entities require application-level joins
- Single-table design adds complexity to the data model
- Less mature migration tooling than Postgres + Alembic

### Open Decisions

- [ ] **Table design**: Single-table (all entities in one table with PK/SK overloading) vs. multi-table (one table per entity)? Single-table is more cost-efficient but harder to reason about.
- [ ] **Access library**: Raw `boto3` vs. `PynamoDB` (ORM-like) vs. `dynamodb-toolbox` (single-table helper)

## ECS Fargate

### Why Fargate

- **No server management**: Define a container, ECS runs it. No EC2 patching.
- **Warm processes**: DuckDB connections stay alive between requests (unlike Lambda cold starts)
- **Right-sized**: Start at 0.5 vCPU / 1GB memory for ~$40/month
- **Horizontal scaling**: ECS auto-scaling on CPU/memory metrics
- **Docker-native**: Standard `Dockerfile`, no vendor-specific runtime

### Why Not Lambda

- DuckDB cold starts are too slow — loading Iceberg metadata and warming the Parquet cache on every cold container creates unacceptable dashboard latency
- Lambda's 15-minute timeout limits simulation run time
- Lambda's ephemeral storage (10GB max) limits Parquet cache size

### Why Not EKS

- Control plane alone costs $73/month before running anything
- Kubernetes operational overhead is unjustified for a small service count
- Revisit only if the platform grows to 50+ services

### Starting Configuration

- 1 Fargate task, 0.5 vCPU / 1GB memory
- ECS auto-scaling policy on CPU > 70%
- Deploy via GitHub Actions → ECR → ECS service update

## Iceberg on S3

### Why Iceberg

The data warehouse already produces Iceberg tables — this is not a new choice but a continuation of existing infrastructure.

- **Schema evolution**: Add/rename/drop columns without rewriting data
- **Partition pruning**: `customer_id` partitions mean DuckDB skips irrelevant tenants' data
- **Time travel**: Query data as of a specific snapshot for point-in-time analytics
- **Snapshot isolation**: Consistent reads even while the data pipeline writes new data

### Glue Catalog Integration

Tables are registered in the AWS Glue Catalog:
- **Account**: `016146521450`
- **Region**: `af-south-1`
- **DuckDB attach**: `ATTACH '016146521450' (TYPE ICEBERG, ENDPOINT_TYPE GLUE)`

## Development Tools

| Tool | Purpose |
|---|---|
| Python 3.12+ | Runtime |
| pip + venv | Package management |
| black | Code formatting |
| ruff | Linting |
| isort | Import sorting |
| pytest | Testing framework |
| mypy or pyright | Type checking |
| pydantic-settings | Configuration management |

## Open Decisions Summary

- [ ] **DynamoDB access library**: Raw boto3, PynamoDB, or dynamodb-toolbox?
- [ ] **DuckDB extension pre-caching**: Pre-install `iceberg` and `httpfs` extensions in Docker image to avoid runtime downloads
- [ ] **Observability**: CloudWatch only, or add OpenTelemetry/X-Ray for distributed tracing?
- [ ] **API versioning**: URL path prefix (`/api/v1/`), API Gateway stages, or header-based?
- [ ] **Rate limiting**: API Gateway throttling only, or additional app-level limits via `slowapi`?
