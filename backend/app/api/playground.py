from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.dal.base import BaseDAL
from app.models.watch_config import WatchConfig

router = APIRouter()


def _get_dal_and_table(env: str, table: str):
    watch_config = WatchConfig.load(settings.watch_config_path)
    env_config = watch_config.get_environment(env)
    if not env_config:
        raise HTTPException(status_code=404, detail=f"Environment '{env}' not found")

    table_cfg = next((t for t in env_config.enabled_tables() if t.table == table), None)
    if not table_cfg:
        raise HTTPException(status_code=404, detail=f"Table '{table}' not watched in '{env}'")

    connection_url = os.environ.get(env_config.connection_env_var)
    if not connection_url:
        raise HTTPException(status_code=500, detail=f"Env var '{env_config.connection_env_var}' not set")

    dal = BaseDAL.from_config(env_config, connection_url)
    return dal, table_cfg


@router.get("/environments/{env}/tables/{table}/schema")
def get_table_schema(env: str, table: str):
    dal, table_cfg = _get_dal_and_table(env, table)
    try:
        schema = dal.fetch_table_schema(table_cfg.schema_name, table)
        return {"table": table, "schema": schema, "primary_key": table_cfg.primary_key}
    finally:
        dal.close()


@router.get("/environments/{env}/tables/{table}/rows")
def get_rows(env: str, table: str):
    dal, table_cfg = _get_dal_and_table(env, table)
    try:
        rows = dal.fetch_rows(table_cfg.schema_name, table)
        return {"table": table, "rows": rows}
    finally:
        dal.close()


class RowPayload(BaseModel):
    data: dict[str, Any]


@router.post("/environments/{env}/tables/{table}/rows", status_code=201)
def insert_row(env: str, table: str, payload: RowPayload):
    dal, table_cfg = _get_dal_and_table(env, table)
    try:
        # Drop empty strings so Postgres can use column defaults
        data = {k: (None if v == "" else v) for k, v in payload.data.items()}
        data = {k: v for k, v in data.items() if v is not None}
        if not data:
            raise HTTPException(status_code=400, detail="No data provided")
        cols = ", ".join(f'"{c}"' for c in data)
        placeholders = ", ".join(f"%(col_{c})s" for c in data)
        sql = f'INSERT INTO "{table_cfg.schema_name}"."{table}" ({cols}) VALUES ({placeholders})'
        params = {f"col_{k}": v for k, v in data.items()}
        dal.execute_dml(sql, params)
        return {"message": f"Row inserted into {table}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        dal.close()


@router.put("/environments/{env}/tables/{table}/rows")
def update_row(env: str, table: str, payload: RowPayload):
    dal, table_cfg = _get_dal_and_table(env, table)
    try:
        pk_cols = set(table_cfg.primary_key)
        set_data = {k: v for k, v in payload.data.items() if k not in pk_cols}
        pk_data = {k: v for k, v in payload.data.items() if k in pk_cols}

        if not set_data:
            raise HTTPException(status_code=400, detail="No non-PK columns to update")
        if not pk_data:
            raise HTTPException(status_code=400, detail="PK columns missing from payload")

        set_clause = ", ".join(f'"{c}" = %(set_{c})s' for c in set_data)
        where_clause = " AND ".join(f'"{c}" = %(pk_{c})s' for c in pk_data)
        sql = f'UPDATE "{table_cfg.schema_name}"."{table}" SET {set_clause} WHERE {where_clause}'
        params = {f"set_{k}": v for k, v in set_data.items()}
        params.update({f"pk_{k}": v for k, v in pk_data.items()})
        dal.execute_dml(sql, params)
        return {"message": f"Row updated in {table}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        dal.close()
