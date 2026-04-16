# Backend Architecture

## Overview

SupSim backend is a serverless multi-tenant supply chain analytics API. The architecture uses AWS Lambda for compute, API Gateway for routing and auth, Athena + AWS Wrangler for analytical queries over Iceberg tables, and DynamoDB for application state.

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
                    │    Lambda    │      ┌───────────┐
                    │  Functions   │◄────►│ DynamoDB  │
                    │  + Shared    │      │ (app state)│
                    │    Layer     │      └───────────┘
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │   Athena     │
                    │ (AWS Wrangler)│
                    └──────┬───────┘
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

This layer is managed by the existing data warehouse pipeline and is read-only from the backend's perspective.

### Query Layer — Athena via AWS Wrangler

AWS Wrangler executes Athena queries against the Glue Catalog / Iceberg tables. This is a managed query service — no engine to provision or warm up.

- **AWS Wrangler**: Python library (via AWS managed Lambda layer) that wraps Athena query execution and returns pandas DataFrames
- **String Formatted Queries**: All queries go through a tenant-scoped query builder that injects `WHERE customer_id = {customer_id}`
- **Athena workgroup**: Controls cost limits, query timeout, and result location

### Compute Layer — Lambda Functions

One Lambda Handler per API endpoint, sharing a common code layer per service (ie. analytics/app.py).

- **Thin handlers**: Each Lambda handles HTTP method routing and delegates to services
- **Shared layer**: PynamoDB models, services, query builders, auth, and utilities
- **AWS managed layer**: AWS SDK for pandas (awswrangler) provided by AWS
- **Architecture**: arm64 (Graviton2) for cost and performance

### Application State — DynamoDB

- **Organisations table**: Tenant meta data and context (PK = customer_id)
- **Stock table**: Stock meta data

### Auth — Cognito + API Gateway

- **Cognito User Pools**: User registration, login, password policies
- **Cognito Groups**: One group per tenant (e.g., `BLI001`)
- **API Gateway JWT Authorizer**: Validates JWT before requests reach Lambda

## Multi-Tenancy Strategy

### Approach: Shared Tables, Partitioned by `customer_id`

All tenants share the same Iceberg tables, partitioned by `customer_id`. This provides:
- **Performance**: Athena only reads Parquet files for the requested tenant (partition pruning)
- **Simplicity**: No per-tenant DDL, schema migrations, or table management
- **Isolation**: Every query is automatically scoped to one tenant's data

### Tenant Resolution Flow

1. User authenticates via Cognito → receives JWT with `cognito:groups` claim
2. API Gateway validates JWT via Cognito JWT authorizer
3. Lambda reads `cognito:groups` from the API Gateway request context
4. DynamoDB Organisations -> extract tenant context and meta data
5. `TenantContext` (frozen dataclass) is constructed and passed to all services
6. Query builder ensures every Athena query includes `WHERE customer_id = :customer_id`

## Data Flow

### Dashboard Queries

```
Client → API Gateway (JWT auth) → Lambda → AWS Wrangler → Athena
  → S3/Iceberg (partition-pruned by customer_id) → response
```

1. API Gateway validates the JWT and forwards the request with user claims
2. Service layer calls query builder which constructs a tenant-scoped SQL query
3. AWS Wrangler executes the query via Athena
4. Athena reads only the relevant Parquet partitions from S3
5. Results are returned as JSON

## Security Model

### Authentication

- **Cognito User Pools**: Manages user registration, login, MFA, password policies
- **Cognito Groups**: One group per tenant, users assigned at onboarding
- **JWT tokens**: Issued by Cognito, include `cognito:groups` claim
- **API Gateway JWT Authorizer**: Validates token signature and expiry before requests reach Lambda

### Authorization

Tenant isolation enforced at multiple layers:
1. **API Gateway**: JWT must be valid
2. **Lambda handler**: Extracts `tenant_group`, resolves `customer_id`
3. **Query builder**: Injects `WHERE customer_id = {customer_id}` into every Athena query
4. **Athena**: Read-only access to data, cannot modify Iceberg tables

### IAM Security

- Each Lambda function has least-privilege IAM policies
- Analytics functions: Athena execute, Glue read, S3 read/write (query results only)
- Organisation functions: DynamoDB CRUD
- User functions: Cognito admin operations scoped to the user pool
