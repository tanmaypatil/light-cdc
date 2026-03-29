"""Unit tests for watch_config.py model parsing."""
import json
import pytest
from pathlib import Path
from app.models.watch_config import WatchConfig


def write_config(tmp_path, data):
    p = tmp_path / "watch.json"
    p.write_text(json.dumps(data))
    return str(p)


MINIMAL = {
    "version": "1",
    "environments": [
        {
            "name": "dev",
            "connection_env_var": "DEV_DATABASE_URL",
            "tables": [
                {"schema": "public", "table": "accounts", "primary_key": ["account_id"]}
            ],
        }
    ],
}


def test_load_minimal_config(tmp_path):
    cfg = WatchConfig.load(write_config(tmp_path, MINIMAL))
    assert cfg.version == "1"
    assert len(cfg.environments) == 1
    assert cfg.environments[0].name == "dev"


def test_defaults(tmp_path):
    cfg = WatchConfig.load(write_config(tmp_path, MINIMAL))
    env = cfg.environments[0]
    assert env.db_type == "postgres"
    assert env.poll_interval_seconds == 1800
    assert env.large_table_threshold == 1000
    table = env.tables[0]
    assert table.exclude_columns == []
    assert table.enabled is True
    assert table.updated_at_column is None


def test_get_environment(tmp_path):
    cfg = WatchConfig.load(write_config(tmp_path, MINIMAL))
    assert cfg.get_environment("dev") is not None
    assert cfg.get_environment("qa") is None


def test_enabled_tables_filters_disabled(tmp_path):
    data = {**MINIMAL}
    data["environments"][0]["tables"] = [
        {"schema": "public", "table": "accounts", "primary_key": ["account_id"], "enabled": True},
        {"schema": "public", "table": "rules", "primary_key": ["rule_id"], "enabled": False},
    ]
    cfg = WatchConfig.load(write_config(tmp_path, data))
    enabled = cfg.environments[0].enabled_tables()
    assert len(enabled) == 1
    assert enabled[0].table == "accounts"


def test_per_table_threshold_override(tmp_path):
    data = {**MINIMAL}
    data["environments"][0]["tables"][0]["large_table_threshold"] = 500
    cfg = WatchConfig.load(write_config(tmp_path, data))
    assert cfg.environments[0].tables[0].large_table_threshold == 500


def test_updated_at_column(tmp_path):
    data = {**MINIMAL}
    data["environments"][0]["tables"][0]["updated_at_column"] = "last_modified"
    cfg = WatchConfig.load(write_config(tmp_path, data))
    assert cfg.environments[0].tables[0].updated_at_column == "last_modified"


def test_multiple_environments(tmp_path):
    data = {
        "version": "1",
        "environments": [
            {"name": "dev", "connection_env_var": "DEV_URL",
             "tables": [{"schema": "public", "table": "accounts", "primary_key": ["account_id"]}]},
            {"name": "qa", "connection_env_var": "QA_URL", "db_type": "oracle",
             "tables": [{"schema": "public", "table": "accounts", "primary_key": ["account_id"]}]},
        ],
    }
    cfg = WatchConfig.load(write_config(tmp_path, data))
    assert cfg.get_environment("qa").db_type == "oracle"


def test_composite_primary_key(tmp_path):
    data = {**MINIMAL}
    data["environments"][0]["tables"][0]["primary_key"] = ["customer_id", "program_code"]
    cfg = WatchConfig.load(write_config(tmp_path, data))
    assert cfg.environments[0].tables[0].primary_key == ["customer_id", "program_code"]
