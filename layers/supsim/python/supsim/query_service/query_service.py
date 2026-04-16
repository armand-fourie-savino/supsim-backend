from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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

    _POLL_INTERVAL_S = 0.25
    _POLL_TIMEOUT_S = 300

    def execute(
        self, boto3_session: boto3.Session | None = None
    ) -> list[dict[str, Any]]:
        """Execute the query via Athena and return rows as dicts."""

        session = boto3_session or boto3.Session()
        client = session.client("athena")

        execution_id = client.start_query_execution(
            QueryString=self.sql,
            QueryExecutionContext={"Database": self.database},
            WorkGroup=self.workgroup,
        )["QueryExecutionId"]

        # Poll until terminal state
        deadline = time.monotonic() + self._POLL_TIMEOUT_S
        state = "RUNNING"
        reason = ""

        while state not in ("SUCCEEDED", "FAILED", "CANCELLED"):
            if time.monotonic() > deadline:
                client.stop_query_execution(QueryExecutionId=execution_id)
                raise TimeoutError(
                    f"Athena query exceeded {self._POLL_TIMEOUT_S}s timeout"
                )
            time.sleep(self._POLL_INTERVAL_S)
            status = client.get_query_execution(QueryExecutionId=execution_id)[
                "QueryExecution"
            ]["Status"]
            state = status["State"]
            reason = status.get("StateChangeReason", "")

        if state != "SUCCEEDED":
            raise RuntimeError(f"Athena query {state}: {reason or 'unknown'}")

        # Fetch first page and extract column headers
        first_page = client.get_query_results(QueryExecutionId=execution_id)
        first_rows = first_page["ResultSet"]["Rows"]
        keys = [col["VarCharValue"] for col in first_rows[0]["Data"]]

        rows: list[dict[str, Any]] = []
        rows.extend(
            dict(zip(keys, (col.get("VarCharValue") for col in row["Data"])))
            for row in first_rows[1:]
        )

        # Paginate remaining pages
        next_token = first_page.get("NextToken")
        while next_token is not None:
            page = client.get_query_results(
                QueryExecutionId=execution_id, NextToken=next_token
            )
            rows.extend(
                dict(zip(keys, (col.get("VarCharValue") for col in row["Data"])))
                for row in page["ResultSet"]["Rows"]
            )
            next_token = page.get("NextToken")

        return rows


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
