"""Aggregates all v1 endpoint routers."""

from fastapi import APIRouter

from supsim.api.v1.endpoints import health

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health.router, tags=["health"])
