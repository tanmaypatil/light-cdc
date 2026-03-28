from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class RetentionConfig(BaseModel):
    max_days: int = 30
    max_size_mb: int = 500


class TableConfig(BaseModel):
    schema_name: str = Field(alias="schema", default="public")
    table: str
    primary_key: list[str]
    exclude_columns: list[str] = []
    enabled: bool = True

    model_config = {"populate_by_name": True}


class EnvironmentConfig(BaseModel):
    name: str
    db_type: Literal["postgres", "oracle"] = "postgres"
    connection_env_var: str
    poll_interval_seconds: int = 1800
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    tables: list[TableConfig]

    def enabled_tables(self) -> list[TableConfig]:
        return [t for t in self.tables if t.enabled]


class WatchConfig(BaseModel):
    version: str
    environments: list[EnvironmentConfig]

    def get_environment(self, name: str) -> EnvironmentConfig | None:
        for env in self.environments:
            if env.name == name:
                return env
        return None

    @classmethod
    def load(cls, path: str | Path) -> "WatchConfig":
        with open(path) as f:
            data = json.load(f)
        return cls.model_validate(data)
