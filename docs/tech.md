# Technology Choices

## Stack Overview

| Component | Technology | Purpose |
|---|---|---|
| IaC | AWS CDk | Infrastructure as code, Lambda packaging and deployment |
| API Gateway | AWS API Gateway HTTP API | JWT auth, rate limiting, routing |
| Authentication | Amazon Cognito | User pools, MFA, JWT issuance |
| Compute | AWS Lambda (arm64) | One function per API endpoint |
| Analytics Engine | AWS Wrangler + Athena | SQL queries over Iceberg tables |
| Table Format | Apache Iceberg | Schema evolution, partition pruning |
| Object Storage | AWS S3 | Iceberg data files (Parquet) + Athena results |
| Metadata Catalog | AWS Glue | Iceberg table registration |
| App State | Amazon DynamoDB | Organisations, app config |
| DynamoDB ORM | PynamoDB | Python model-based DynamoDB access |
| CI/CD | GitHub Actions | Build, test, deploy pipeline |
| Logging | Amazon CloudWatch | Structured JSON logs |
| Package Manager | pip + SAM build | Dependency management |

## AWS SAM

### Why SAM

- **Lambda-native**: First-class support for Lambda functions, layers, and API Gateway
- **Single template**: All resources (Cognito, API GW, Lambda, DynamoDB, IAM) in one `template.yaml`
- **Local development**: `sam local invoke` and `sam local start-api` for testing without deployment
- **Build system**: `sam build` handles dependency installation per function and layer
- **CloudFormation-based**: Full access to CloudFormation resources when needed

### Why CDK

- CDK is much more customisable

## Lambda (Compute)

### Why Lambda

- **Zero idle cost**: Pay only for invocations, scales to zero
- **No infrastructure**: No ECS tasks, Docker images, or container orchestration
- **Per-endpoint isolation**: One function per endpoint, independent scaling and IAM policies
- **Managed concurrency**: AWS handles scaling automatically

### Architecture: arm64 (Graviton2)

- ~20% cheaper than x86
- Equivalent or better performance for Python workloads

### Cold Start Considerations

- AWS Wrangler layer is large (~250MB with pandas/pyarrow)
- Using the AWS managed layer avoids building this ourselves
- Cold starts estimated at 3-8 seconds; acceptable for early stage
- Can add provisioned concurrency later for latency-sensitive paths

## AWS Wrangler + Athena

### Why Athena over DuckDB

The previous architecture used embedded DuckDB. We switched to Athena because:

- **No process lifecycle**: Athena is a managed service — no connection to warm up on cold start
- **Lambda-compatible**: No long-lived DuckDB connection or file caching needed
- **Simpler architecture**: No ThreadPoolExecutor, no in-process state
- **Partition pruning**: Athena natively prunes Iceberg partitions via Glue Catalog

### Tradeoffs

- **Latency**: Athena queries take 2-5 seconds vs. sub-second DuckDB. Acceptable for analytics dashboards.
- **Cost**: ~$5/TB scanned. With partition pruning by `customer_id`, per-query cost is minimal.
- **No local caching**: Each query scans S3. Athena query result reuse helps for repeated queries.

## PynamoDB (DynamoDB ORM)

### Why PynamoDB

- **Model-based**: Define DynamoDB tables as Python classes with typed attributes
- **Pythonic API**: `Model.get()`, `Model.query()`, `Model.update()` instead of raw boto3
- **Validation**: Type checking on attributes before writes
- **Condition expressions**: Clean syntax for conditional writes

### Decision: Multi-Table over Single-Table

For an early-stage product with PynamoDB as the ORM:
- Multi-table is clearer and easier to test
- PynamoDB maps naturally to one model class per table
- Revisit single-table if cross-entity transactions become a bottleneck

## Amazon Cognito

### Why Cognito

- **Managed user pools**: Handles signup, login, password reset, MFA without custom code
- **JWT issuance**: Tokens include `cognito:groups` claim used for tenant resolution
- **API Gateway integration**: Native JWT authorizer — no auth code in Lambda
- **Groups for multi-tenancy**: One Cognito group per tenant, users assigned at onboarding

## DynamoDB

### Why DynamoDB over Postgres

- **Fully serverless**: Pay-per-request pricing, scales to zero cost with no traffic
- **No fixed costs**: vs. RDS minimum ~$12/month even idle
- **Single-digit ms latency**: Fast for key-value lookups (tenant config)
- **Managed backups**: Point-in-time recovery built-in

## Iceberg on S3

### Why Iceberg

The data warehouse already produces Iceberg tables — this is not a new choice but a continuation of existing infrastructure.

- **Schema evolution**: Add/rename/drop columns without rewriting data
- **Partition pruning**: `customer_id` partitions mean Athena skips irrelevant tenants' data
- **Snapshot isolation**: Consistent reads even while the data pipeline writes new data

### Glue Catalog Integration

Tables are registered in the AWS Glue Catalog:
- **Account**: `016146521450`
- **Region**: `af-south-1`

## Development Tools

| Tool | Purpose |
|---|---|
| Python 3.12+ | Runtime |
| pip + venv | Package management |
| ruff | Linting + formatting |
| pytest | Testing framework |
| mypy | Type checking |
| moto | AWS service mocking for tests |
| AWS CDK | Local Lambda testing and deployment |

## GitHub Actions CI/CD

- **test.yml**: On PR — lint, type check, pytest
- **deploy.yml**: On push to main — sam build + sam deploy to dev environment
- AWS credentials via OIDC role assumption
