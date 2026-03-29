from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.watch_config import EnvironmentConfig


class BaseDAL(ABC):
    """Abstract data access layer. One instance per environment connection."""

    @abstractmethod
    def fetch_table(
        self,
        schema: str,
        table: str,
        exclude_columns: list[str],
    ) -> list[dict]:
        """Return all rows from schema.table, excluding specified columns."""

    @abstractmethod
    def fetch_table_since(
        self,
        schema: str,
        table: str,
        exclude_columns: list[str],
        updated_at_col: str,
        since: str,
    ) -> list[dict]:
        """Return rows where updated_at_col > since (ISO-8601 string). Used for large-table incremental polling."""

    @abstractmethod
    def fetch_row_count(self, schema: str, table: str) -> int:
        """Return the current row count for schema.table."""

    @abstractmethod
    def fetch_table_checksum(self, schema: str, table: str, primary_key: list[str]) -> str:
        """Return a scalar checksum representing the current state of the table.
        Used as a cheap gate: if unchanged since last poll, skip full fetch."""

    @abstractmethod
    def fetch_table_schema(self, schema: str, table: str) -> list[dict]:
        """Return column metadata from information_schema."""

    @abstractmethod
    def fetch_rows(self, schema: str, table: str) -> list[dict]:
        """Return up to 100 rows from schema.table."""

    @abstractmethod
    def fetch_raw(self, sql: str) -> list[dict]:
        """Execute a raw SELECT and return rows as dicts."""

    @abstractmethod
    def execute_dml(self, sql: str, params: dict) -> int:
        """Execute a single DML statement; return rows affected."""

    @abstractmethod
    def test_connection(self) -> bool:
        """Return True if the connection is alive."""

    @abstractmethod
    def close(self) -> None:
        """Release the connection."""

    @classmethod
    def from_config(cls, env_config: "EnvironmentConfig", connection_url: str) -> "BaseDAL":
        """Factory: returns the right DAL subclass based on env_config.db_type."""
        from app.dal.postgres_dal import PostgresDAL

        if env_config.db_type == "postgres":
            return PostgresDAL(connection_url)
        if env_config.db_type == "oracle":
            from app.dal.oracle_dal import OracleDAL
            return OracleDAL(connection_url)
        raise ValueError(f"Unknown db_type: {env_config.db_type}")
