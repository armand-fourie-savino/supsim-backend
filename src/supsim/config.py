"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # AWS
    aws_region: str = "af-south-1"
    aws_account_id: str = "016146521450"
    aws_profile: str | None = None  # None = IAM role (ECS). Set for local dev.

    # DuckDB
    duckdb_memory_limit: str = "512MB"
    duckdb_threads: int = 2

    # Application
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
