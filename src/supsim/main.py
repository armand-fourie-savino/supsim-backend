"""FastAPI application factory with lifespan events."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from supsim.api.v1.router import v1_router
from supsim.config import get_settings
from supsim.db.duckdb.connection import DuckDBManager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    # Startup — DuckDB connection
    duckdb_manager = DuckDBManager(settings)
    try:
        await duckdb_manager.connect()
    except Exception:
        logger.warning(
            "DuckDB failed to connect — app will start in degraded mode. "
            "The /ready endpoint will return 503.",
            exc_info=True,
        )
        duckdb_manager = None  # type: ignore[assignment]

    app.state.duckdb_manager = duckdb_manager

    yield

    # Shutdown
    if duckdb_manager is not None:
        await duckdb_manager.close()


def create_app() -> FastAPI:
    app = FastAPI(
        title="SupSim Backend",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.include_router(v1_router)
    return app


app = create_app()
