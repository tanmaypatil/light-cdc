from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass
class RowSnapshot:
    pk_value: str    # JSON-serialized PK dict e.g. '{"account_id": 1}'
    row_data: str    # JSON-serialized row (exclude_columns already stripped)
    row_hash: str    # SHA-256 of row_data


@dataclass
class ChangeEvent:
    table_name: str
    pk_value: str
    change_type: str          # 'INSERT' | 'UPDATE' | 'DELETE'
    before_data: str | None   # None for INSERT
    after_data: str | None    # None for DELETE
    diff_columns: list[str]   # empty for INSERT/DELETE


def make_pk_value(row: dict, primary_key: list[str]) -> str:
    return json.dumps({k: row[k] for k in primary_key}, sort_keys=True, default=str)


def make_row_hash(row_data: dict) -> str:
    serialized = json.dumps(row_data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


def make_snapshot(row: dict, primary_key: list[str]) -> RowSnapshot:
    pk_value = make_pk_value(row, primary_key)
    row_hash = make_row_hash(row)
    return RowSnapshot(
        pk_value=pk_value,
        row_data=json.dumps(row, sort_keys=True, default=str),
        row_hash=row_hash,
    )


def rows_to_snapshots(rows: list[dict], primary_key: list[str]) -> list[RowSnapshot]:
    return [make_snapshot(row, primary_key) for row in rows]


def compute_diff(
    table_name: str,
    previous: list[RowSnapshot],
    current: list[RowSnapshot],
) -> list[ChangeEvent]:
    """
    Pure function. Compares two snapshot lists and returns change events.
    No I/O — safe to unit-test in isolation.
    """
    prev_by_pk: dict[str, RowSnapshot] = {s.pk_value: s for s in previous}
    curr_by_pk: dict[str, RowSnapshot] = {s.pk_value: s for s in current}

    events: list[ChangeEvent] = []

    # INSERTs: in current but not in previous
    for pk, snap in curr_by_pk.items():
        if pk not in prev_by_pk:
            events.append(ChangeEvent(
                table_name=table_name,
                pk_value=pk,
                change_type="INSERT",
                before_data=None,
                after_data=snap.row_data,
                diff_columns=[],
            ))

    # DELETEs: in previous but not in current
    for pk, snap in prev_by_pk.items():
        if pk not in curr_by_pk:
            events.append(ChangeEvent(
                table_name=table_name,
                pk_value=pk,
                change_type="DELETE",
                before_data=snap.row_data,
                after_data=None,
                diff_columns=[],
            ))

    # UPDATEs: in both but hash differs
    for pk in prev_by_pk.keys() & curr_by_pk.keys():
        prev_snap = prev_by_pk[pk]
        curr_snap = curr_by_pk[pk]
        if prev_snap.row_hash != curr_snap.row_hash:
            diff_columns = _column_diff(prev_snap.row_data, curr_snap.row_data)
            events.append(ChangeEvent(
                table_name=table_name,
                pk_value=pk,
                change_type="UPDATE",
                before_data=prev_snap.row_data,
                after_data=curr_snap.row_data,
                diff_columns=diff_columns,
            ))

    return events


def _column_diff(before_json: str, after_json: str) -> list[str]:
    before: dict[str, Any] = json.loads(before_json)
    after: dict[str, Any] = json.loads(after_json)
    return [col for col in after if str(before.get(col)) != str(after.get(col))]
