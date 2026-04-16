# Project Structure

## Directory Layout

```
supsim-backend/
├── app.py                            # CDK app entry point — wires stacks together
├── cdk.json                          # CDK configuration and feature flags
├── requirements.txt                  # CDK runtime dependencies
├── requirements-dev.txt              # Dev/test dependencies
├── source.bat                        # Windows venv activation helper
│
├── stacks/                           # AWS CDK stack definitions
│   ├── iam_stack.py                  # IAM roles and policies for Lambda execution
│   ├── api_stack.py                  # HTTP API Gateway with CORS config
│   ├── lambda_stack.py               # Lambda functions and API route bindings
│   └── database_stack.py             # DynamoDB tables (empty — to be built)
│
├── lambdas/                          # One directory per Lambda function
│   └── health/
│       └── app.py                    # GET /health (unauthenticated)
│
├── layers/                           # Shared Lambda layer (empty — to be built)
│   └── supsim/
│       └── python/
│           └── supsim/
│               └── query_service/    # Athena query service (empty — to be built)
│
├── tests/
│   └── unit/
│       └── test_supsim_backend_stack.py  # CDK stack synthesis test (placeholder)
│
└── docs/
    ├── architecture.md               # System architecture and data flow
    ├── tech.md                       # Technology choices and justifications
    ├── api-conventions.md            # API design conventions
    ├── query-builder.md              # Athena query builder design
    └── structure.md                  # This file
```

## Module Responsibilities

### CDK App Entry Point (`app.py`)

Creates the CDK app and wires three stacks together with explicit dependencies:

1. **IamStack** — shared IAM roles (no dependencies)
2. **ApiStack** — HTTP API Gateway (no dependencies)
3. **LambdaStack** — Lambda functions and route bindings (depends on IamStack and ApiStack)

### CDK Stacks (`stacks/`)

Each stack is a single-purpose CDK construct that defines one slice of infrastructure.

#### `iam_stack.py` — IAM

Defines `supsim-lambda-execution-role` with managed policies for Lambda basic execution, S3, Athena, and Glue access. All Lambda functions share this role.

#### `api_stack.py` — API Gateway

Creates the `supsim-api` HTTP API with CORS preflight configured for all standard methods and `Authorization`/`Content-Type` headers. Exposes `self.http_api` for the Lambda stack to bind routes.

#### `lambda_stack.py` — Lambda Functions

Defines Lambda functions (Python 3.12, ARM64) and binds each to an HTTP API route. Currently contains the health function at `GET /health`.

#### `database_stack.py` — DynamoDB

Placeholder for DynamoDB table definitions. Will contain Organisations and Stock tables.

### Lambda Handlers (`lambdas/`)

Each function is a thin handler: parse the event, delegate to a shared service, return the response. No business logic lives in handlers.

Currently only the health endpoint exists. Additional Lambda functions will be added incrementally.

### Shared Layer (`layers/supsim/`)

Placeholder for shared business logic, data access, and utilities available to every Lambda function at runtime. Will contain:

- **query_service/** — Athena query execution via AWS Wrangler with tenant-scoped query building

### Tests (`tests/`)

Contains a placeholder CDK stack synthesis test. Test infrastructure will expand as Lambda functions and services are built.
