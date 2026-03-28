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
    def execute_dml(self, sql: str, params: dict) -> None:
        """Execute a single DML statement (UPDATE / INSERT / DELETE) for rollback."""

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
            raise NotImplementedError("Oracle DAL is not yet implemented")
        raise ValueError(f"Unknown db_type: {env_config.db_type}")
