from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import awswrangler as wr
import boto3

# ---------------------------------------------------------------------------
# Template loading — cached at module level for Lambda container reuse
# ---------------------------------------------------------------------------

_TEMPLATE_DIR = Path(__file__).parent / "templates"

_TEMPLATES: dict[str, str] = {
    "stock_summary": (_TEMPLATE_DIR / "stock_summary.sql").read_text(),
    "movement_metrics": (_TEMPLATE_DIR / "movement_metrics.sql").read_text(),
    "customer_summary": (_TEMPLATE_DIR / "customer_summary.sql").read_text(),
}


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Query:
    """A fully-formatted SQL query with Athena execution context."""

    sql: str
    database: str = "supsim"
    workgroup: str = "primary"

    def execute(
        self, boto3_session: boto3.Session | None = None
    ) -> list[dict[str, Any]]:
        """Execute the query via Athena and return rows as dicts."""

        df = wr.athena.read_sql_query(
            sql=self.sql,
            database=self.database,
            workgroup=self.workgroup,
            boto3_session=boto3_session,
        )

        return df.to_dict(orient="records")


# ---------------------------------------------------------------------------
# QueryBuilder
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class QueryBuilder:
    """Build tenant-scoped Athena queries from SQL templates."""

    customer_id: str
    database: str = "supsim"
    workgroup: str = "primary"

    def build_stock_summary_query(self) -> Query:
        sql = _TEMPLATES["stock_summary"].format(customer_id=self.customer_id)
        return Query(sql=sql, database=self.database, workgroup=self.workgroup)

    def build_movement_metrics_query(self, stock_code: str) -> Query:
        sql = _TEMPLATES["movement_metrics"].format(
            customer_id=self.customer_id,
            stock_code=stock_code,
        )
        return Query(sql=sql, database=self.database, workgroup=self.workgroup)

    def build_customer_summary_query(self) -> Query:
        sql = _TEMPLATES["customer_summary"].format(customer_id=self.customer_id)
        return Query(sql=sql, database=self.database, workgroup=self.workgroup)
