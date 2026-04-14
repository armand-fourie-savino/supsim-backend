# SupSim Backend

## Local Development

### Prerequisites

- Python 3.12+

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
source .venv/Scripts/activate  # Windows (Git Bash)

pip install -e ".[dev]"
```

### Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Set `AWS_PROFILE` to your local AWS profile name if you want DuckDB to connect to the Glue Catalog. Leave it empty to start in degraded mode (the app runs, but `/api/v1/ready` returns 503).

### Run the Server

```bash
uvicorn supsim.main:app --reload
```

The API is available at `http://localhost:8000`. OpenAPI docs at `http://localhost:8000/docs`.

### Test Endpoints

```bash
# Liveness check (always 200)
curl http://localhost:8000/api/v1/health

# Readiness check (200 if DuckDB connected, 503 otherwise)
curl http://localhost:8000/api/v1/ready
```

### Linting

```bash
black --check src/
ruff check src/
```
