"""DuckDB connection lifecycle management.

Manages a single DuckDB connection per process: extension loading,
AWS credential setup, and Glue Catalog attachment.
"""

import logging

import boto3
import duckdb

from supsim.config import Settings

logger = logging.getLogger(__name__)


class DuckDBManager:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._con: duckdb.DuckDBPyConnection | None = None

    @property
    def _conn(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            raise RuntimeError("DuckDB not connected. Call connect() first.")
        return self._con

    async def connect(self) -> None:
        """Initialise DuckDB: extensions, AWS secret, Glue Catalog."""
        self._con = duckdb.connect()
        self._configure()
        self._load_extensions()
        self._create_aws_secret()
        self._attach_glue_catalog()
        logger.info("DuckDB connected and Glue Catalog attached")

    def _configure(self) -> None:
        self._conn.execute(f"SET memory_limit = '{self._settings.duckdb_memory_limit}'")
        self._conn.execute(f"SET threads = {self._settings.duckdb_threads}")

    def _load_extensions(self) -> None:
        self._conn.execute("LOAD iceberg;")
        self._conn.execute("LOAD httpfs;")

    def _create_aws_secret(self) -> None:
        session = boto3.Session(
            profile_name=self._settings.aws_profile,
            region_name=self._settings.aws_region,
        )
        credentials = session.get_credentials().get_frozen_credentials()

        # Include SESSION_TOKEN for temporary credentials (ECS task roles).
        token_clause = (
            f"SESSION_TOKEN '{credentials.token}'," if credentials.token else ""
        )
        secret_sql = f"""
            CREATE SECRET aws_secret (
                TYPE S3,
                KEY_ID '{credentials.access_key}',
                SECRET '{credentials.secret_key}',
                {token_clause}
                REGION '{self._settings.aws_region}'
            );
        """
        self._conn.execute(secret_sql)

    def _attach_glue_catalog(self) -> None:
        self._conn.execute(
            f"ATTACH '{self._settings.aws_account_id}' "
            f"(TYPE ICEBERG, ENDPOINT_TYPE GLUE);"
        )

    def get_connection(self) -> duckdb.DuckDBPyConnection:
        return self._conn

    def is_healthy(self) -> bool:
        """Readiness probe: can DuckDB execute a trivial query?"""
        if self._con is None:
            return False
        try:
            result = self._con.execute("SELECT 1").fetchone()
            return result == (1,)
        except Exception:
            return False

    async def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None
            logger.info("DuckDB connection closed")
