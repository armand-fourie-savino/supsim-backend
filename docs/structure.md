# Project Structure

## Directory Layout

```
supsim-backend/
├── template.yaml                     # SAM template (Cognito, API GW, Lambda, Layer)
├── samconfig.toml                    # Per-environment deploy config
├── pyproject.toml                    # Dev tooling config (ruff, mypy, pytest)
├── .env.example                      # Environment variable template
│
├── layers/
│   └── supsim/
│       ├── requirements.txt          # Layer runtime dependencies
│       └── python/
│           └── supsim/               # Shared code available to all Lambda functions
│               ├── config.py         # Environment-based settings
│               ├── models/
│               │   ├── dynamo/       # PynamoDB table models (empty — to be built)
│               │   └── schemas/      # Pydantic request/response models (empty — to be built)
│               ├── services/
│               │   └── analytics.py  # AWS Wrangler + Athena query execution (base only)
│               ├── queries/          # Athena SQL query definitions (empty — to be built)
│               └── utils/
│                   ├── response.py   # Lambda JSON response builders
│                   ├── errors.py     # Custom exception hierarchy
│                   └── logging.py    # Structured JSON logging
│
├── functions/                        # One directory per Lambda function
│   └── health/
│       └── app.py                    # GET /health (unauthenticated)
│
├── tests/                            # Empty — to be built
│
├── docs/
│   ├── architecture.md               # System architecture and data flow
│   ├── tech.md                       # Technology choices and justifications
│   └── structure.md                  # This file
│
└── .github/
    └── workflows/
        ├── test.yml                  # PR: lint + type check + pytest
        └── deploy.yml                # Push to main: sam build + sam deploy
```

## Module Responsibilities

### Lambda Handlers (`functions/`)

Each function is a thin handler: parse the HTTP method, delegate to a shared service, return the response. No business logic lives in handlers.

Currently only the health endpoint exists. Additional Lambda functions will be added incrementally.

### Shared Layer (`layers/supsim/`)

All business logic, data access, and utilities live in the shared layer, available to every Lambda function at runtime.

#### `config.py` — Configuration

Frozen dataclass loading from environment variables. Lambda environment variables are set by SAM template and include Athena/Glue settings and Cognito pool ID.

#### `services/analytics.py` — Analytics Queries

Base analytics service with AWS Wrangler + Athena query execution. Query methods will be added as endpoints are built.

#### `utils/` — Cross-Cutting Utilities

- `response.py`: Standard Lambda proxy response builders with CORS headers
- `errors.py`: Custom exception hierarchy (AppError, NotFoundError, ValidationError, UnauthorizedError, ForbiddenError)
- `logging.py`: JSON-formatted structured logging

### Placeholder Directories

These directories exist but are empty, ready for incremental build-out:

- `models/dynamo/` — PynamoDB table models
- `models/schemas/` — Pydantic request/response models
- `queries/` — Athena SQL query definitions and tenant-scoped query builder
