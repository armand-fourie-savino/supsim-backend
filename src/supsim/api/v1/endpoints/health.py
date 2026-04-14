"""Health and readiness endpoints."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness check. Returns 200 if the process is running."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness check. Verifies DuckDB connection is alive."""
    duckdb_manager = request.app.state.duckdb_manager

    if duckdb_manager is not None and duckdb_manager.is_healthy():
        return JSONResponse({"status": "ready", "duckdb": "connected"})

    return JSONResponse(
        {"status": "not_ready", "duckdb": "disconnected"},
        status_code=503,
    )
