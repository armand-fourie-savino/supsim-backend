from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    environment: str
    glue_database: str
    athena_workgroup: str
    athena_output_bucket: str
    cognito_user_pool_id: str
    log_level: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        environment=os.environ.get("ENVIRONMENT", "dev"),
        glue_database=os.environ["GLUE_DATABASE"],
        athena_workgroup=os.environ["ATHENA_WORKGROUP"],
        athena_output_bucket=os.environ["ATHENA_OUTPUT_BUCKET"],
        cognito_user_pool_id=os.environ.get("COGNITO_USER_POOL_ID", ""),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
