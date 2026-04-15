# SupSim Backend

Serverless supply chain analytics API built with AWS SAM, Lambda, and Athena.

## Architecture

- **Auth**: AWS Cognito (1 group per organisation)
- **API**: API Gateway HTTP API with JWT authorizer
- **Compute**: Lambda (one function per endpoint, shared code layer)
- **Analytics**: AWS Wrangler → Athena → Glue Catalog → Iceberg → S3
- **App State**: DynamoDB (PynamoDB ORM)
- **IaC**: AWS SAM
- **CI/CD**: GitHub Actions

## Prerequisites

- Python 3.12+
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html)
- AWS credentials configured (`aws configure` or environment variables)

## Local Development

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
source .venv/Scripts/activate  # Windows (Git Bash)

pip install -e ".[dev]"
pip install -r layers/shared/requirements.txt
```

### Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

### Run Tests

```bash
pytest tests/ -v
```

### Lint & Type Check

```bash
ruff check .
mypy layers/ functions/
```

### Local API (SAM)

```bash
sam build
sam local start-api
```

Test the health endpoint:

```bash
curl http://localhost:3000/health
```

### Invoke a Single Function

```bash
sam local invoke HealthFunction --event tests/events/health_get.json
```

## Deploy

### First-Time Setup

```bash
sam build
sam deploy --guided
```

### Subsequent Deploys

```bash
sam build && sam deploy --config-env dev
```

## Project Structure

See [docs/structure.md](docs/structure.md) for detailed documentation.

```
template.yaml          # SAM template (all AWS resources)
layers/shared/         # Shared code layer (services, models, utils)
functions/             # Lambda handlers (one per endpoint)
tests/                 # Unit tests and sample events
.github/workflows/     # CI/CD pipelines
```

## API Endpoints

| Endpoint | Methods | Auth | Description |
|---|---|---|---|
| `/health` | GET | None | Health check |
| `/stocks` | GET | Cognito | Stock levels |
| `/stocks/{sku_id}` | GET | Cognito | Stock for specific SKU |
| `/burn-rates` | GET | Cognito | Burn rates / demand forecasts |
| `/incoming` | GET | Cognito | Incoming stock and orders |
| `/organisations` | GET, PUT | Cognito | Organisation management |
| `/users` | GET, POST | Cognito | User management |
| `/users/{user_id}` | DELETE | Cognito | Delete user |
