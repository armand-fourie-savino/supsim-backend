from __future__ import annotations

from typing import Any

import awswrangler as wr

from supsim.config import get_settings
from supsim.utils.logging import get_logger

logger = get_logger(__name__)


class AnalyticsService:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _execute_query(
        self, sql: str, params: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Execute a parameterized Athena query and return records."""

        df = wr.athena.read_sql_query(
            sql=sql,
            database=self.settings.glue_database,
            workgroup=self.settings.athena_workgroup,
            params=params,
            ctas_approach=False,
            s3_output=f"s3://{self.settings.athena_output_bucket}/query-results/",
        )
        
        return df.to_dict(orient="records")  # type: ignore[no-any-return]
