"""Load BuildingConnected ``lead_estimates`` rows from a bc_projects-style CSV."""
from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models.lead_estimate import LeadEstimate


def _blank_to_none(s: str | None) -> str | None:
    if s is None:
        return None
    stripped = s.strip()
    return None if stripped == "" else stripped


def _normalize_csv_row(row: dict[str, str | None]) -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for k, v in row.items():
        key = (k or "").strip()
        if not key:
            continue
        if v is None:
            out[key] = None
        else:
            stripped = v.strip()
            out[key] = None if stripped == "" else stripped
    return out


def _parse_bool(raw: str | None) -> bool | None:
    s = _blank_to_none(raw)
    if s is None:
        return None
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    return None


def _parse_datetime(raw: str | None) -> datetime | None:
    s = _blank_to_none(raw)
    if s is None:
        return None
    iso = s.replace("Z", "+00:00") if s.endswith("Z") else s
    try:
        return datetime.fromisoformat(iso)
    except ValueError:
        return None


def _parse_int(raw: str | None) -> int | None:
    s = _blank_to_none(raw)
    if s is None:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_decimal(raw: str | None) -> Decimal | None:
    s = _blank_to_none(raw)
    if s is None:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _parse_json_column(_key: str, raw: str | None) -> tuple[Any | None, bool]:
    s = _blank_to_none(raw)
    if s is None:
        return None, True
    try:
        return json.loads(s), True
    except json.JSONDecodeError:
        return None, False


def _json_safe_raw_row(norm: dict[str, str | None]) -> dict[str, Any]:
    return {k: (v if v is not None else None) for k, v in norm.items()}


def _csv_row_to_db_row(norm: dict[str, str | None]) -> dict[str, Any]:
    def jfield(csv_key: str, db_key: str, out: dict[str, Any]) -> None:
        val, _ok = _parse_json_column(csv_key, norm.get(csv_key))
        out[db_key] = val

    row: dict[str, Any] = {}

    ext = _blank_to_none(norm.get("id"))
    row["external_id"] = ext

    row["external_parent_id"] = _blank_to_none(norm.get("parentId"))
    row["name"] = _blank_to_none(norm.get("name"))
    row["number"] = _blank_to_none(norm.get("number"))
    row["trade_name"] = _blank_to_none(norm.get("tradeName"))
    row["submission_state"] = _blank_to_none(norm.get("submissionState"))

    jfield("outcome", "outcome", row)
    row["due_at"] = _parse_datetime(norm.get("dueAt"))
    row["bc_updated_at"] = _parse_datetime(norm.get("updatedAt"))
    row["bc_created_at"] = _parse_datetime(norm.get("createdAt"))
    row["is_archived"] = _parse_bool(norm.get("isArchived"))
    row["final_value"] = _parse_decimal(norm.get("finalValue"))
    jfield("additionalInfo", "additional_info", row)
    row["architect"] = _blank_to_none(norm.get("architect"))
    row["average_crew_size"] = _parse_int(norm.get("averageCrewSize"))
    jfield("bid", "bid", row)
    jfield("client", "client", row)
    jfield("clientValues", "client_values", row)
    jfield("competitors", "competitors", row)
    row["contract_duration"] = _parse_int(norm.get("contractDuration"))
    row["contract_start_at"] = _parse_datetime(norm.get("contractStartAt"))
    jfield("customTags", "custom_tags", row)
    jfield("declineReasons", "decline_reasons", row)
    row["default_currency"] = _blank_to_none(norm.get("defaultCurrency"))
    row["engineer"] = _blank_to_none(norm.get("engineer"))
    row["estimating_hours"] = _parse_decimal(norm.get("estimatingHours"))
    row["expected_finish_at"] = _parse_datetime(norm.get("expectedFinishAt"))
    row["expected_start_at"] = _parse_datetime(norm.get("expectedStartAt"))
    row["fee_percentage"] = _parse_decimal(norm.get("feePercentage"))
    row["follow_up_at"] = _parse_datetime(norm.get("followUpAt"))
    jfield("groupChildren", "group_children", row)
    row["invited_at"] = _parse_datetime(norm.get("invitedAt"))
    row["is_nda_required"] = _parse_bool(norm.get("isNdaRequired"))
    row["is_parent"] = _parse_bool(norm.get("isParent"))
    row["is_sealed_bidding"] = _parse_bool(norm.get("isSealedBidding"))
    row["job_walk_at"] = _parse_datetime(norm.get("jobWalkAt"))
    jfield("location", "location", row)
    row["market_sector"] = _blank_to_none(norm.get("marketSector"))
    jfield("members", "members", row)
    row["owning_office_id"] = _blank_to_none(norm.get("owningOfficeId"))
    row["priority"] = _blank_to_none(norm.get("priority"))
    row["profit_margin"] = _parse_decimal(norm.get("profitMargin"))
    row["project_information"] = _blank_to_none(norm.get("projectInformation"))
    row["project_is_public"] = _parse_bool(norm.get("projectIsPublic"))
    row["project_size"] = _parse_decimal(norm.get("projectSize"))
    row["property_owner"] = _blank_to_none(norm.get("propertyOwner"))
    row["property_tenant"] = _blank_to_none(norm.get("propertyTenant"))
    row["request_type"] = _blank_to_none(norm.get("requestType"))
    row["rfis_due_at"] = _parse_datetime(norm.get("rfisDueAt"))
    row["rom"] = _parse_decimal(norm.get("rom"))
    row["source"] = _blank_to_none(norm.get("source"))
    row["trade_specific_instructions"] = _blank_to_none(norm.get("tradeSpecificInstructions"))
    row["win_probability"] = _parse_decimal(norm.get("winProbability"))
    row["workflow_bucket"] = _blank_to_none(norm.get("workflowBucket"))

    row["raw_row"] = _json_safe_raw_row(norm)

    return row


def bc_api_value_to_csv_str(_key: str, val: Any) -> str | None:
    """Coerce a JSON value from the BC API into the string shape ``_csv_row_to_db_row`` expects."""
    if val is None:
        return None
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float, Decimal)):
        return str(val)
    if isinstance(val, dict | list):
        return json.dumps(val, default=str)
    if isinstance(val, datetime):
        s = val.isoformat()
        if val.tzinfo is None:
            return s + "Z"
        return s.replace("+00:00", "Z")
    if isinstance(val, date):
        return val.isoformat()
    return str(val)


def bc_api_project_to_norm(project: Mapping[str, Any]) -> dict[str, str | None]:
    """Flatten a BC ``GET /projects`` result item to CSV-style string fields."""
    out: dict[str, str | None] = {}
    for k, v in project.items():
        if not isinstance(k, str) or k.startswith("_"):
            continue
        out[k] = bc_api_value_to_csv_str(k, v)
    return out


def upsert_lead_estimate_norm_rows(
    sess: Session,
    norms: Iterable[dict[str, str | None]],
    *,
    batch_size: int = 500,
) -> tuple[int, int, int]:
    """Upsert ``lead_estimates`` from CSV-shaped normal rows (same keys as ``_csv_row_to_db_row``)."""
    table = LeadEstimate.__table__
    exclude_update = {"id", "created_at"}
    update_col_names = [c.name for c in table.columns if c.name not in exclude_update]

    loaded = 0
    skipped = 0
    errors = 0
    batch: list[dict[str, Any]] = []

    for norm in norms:
        ext = _blank_to_none(norm.get("id"))
        if ext is None:
            skipped += 1
            continue
        try:
            row = _csv_row_to_db_row(norm)
            row["external_id"] = ext
        except Exception:
            errors += 1
            continue
        batch.append(row)
        if len(batch) >= batch_size:
            _flush_batch(sess, table, batch, mode="upsert", update_col_names=update_col_names)
            loaded += len(batch)
            batch.clear()

    if batch:
        _flush_batch(sess, table, batch, mode="upsert", update_col_names=update_col_names)
        loaded += len(batch)

    return loaded, skipped, errors


def _flush_batch(
    sess: Session,
    table: Any,
    batch: list[dict[str, Any]],
    *,
    mode: str,
    update_col_names: list[str],
) -> None:
    if not batch:
        return
    if mode == "truncate":
        sess.execute(pg_insert(table).values(batch))
        sess.commit()
        return

    ins = pg_insert(table).values(batch)
    set_: dict[str, Any] = {}
    for name in update_col_names:
        if name == "updated_at":
            set_[name] = func.now()
        else:
            set_[name] = getattr(ins.excluded, name)
    ins = ins.on_conflict_do_update(index_elements=["external_id"], set_=set_)
    sess.execute(ins)
    sess.commit()


def load_lead_estimates_csv(
    sess: Session,
    csv_path: str | Path,
    *,
    mode: str = "upsert",
    batch_size: int = 1000,
) -> tuple[int, int, int]:
    """Stream CSV into ``lead_estimates``. Returns ``(loaded, skipped, errors)``."""
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(str(path))

    table = LeadEstimate.__table__
    exclude_update = {"id", "created_at"}
    update_col_names = [c.name for c in table.columns if c.name not in exclude_update]

    loaded = 0
    skipped = 0
    errors = 0
    batch_num = 0
    batch: list[dict[str, Any]] = []

    if mode == "truncate":
        sess.execute(text("TRUNCATE lead_estimates RESTART IDENTITY"))
        sess.commit()

    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            norm = _normalize_csv_row(raw)
            ext = _blank_to_none(norm.get("id"))
            if ext is None:
                skipped += 1
                continue
            try:
                row = _csv_row_to_db_row(norm)
                row["external_id"] = ext
            except Exception:
                errors += 1
                continue

            batch.append(row)
            if len(batch) >= batch_size:
                batch_num += 1
                _flush_batch(sess, table, batch, mode=mode, update_col_names=update_col_names)
                loaded += len(batch)
                batch.clear()

        if batch:
            batch_num += 1
            _flush_batch(sess, table, batch, mode=mode, update_col_names=update_col_names)
            loaded += len(batch)
            batch.clear()

    return loaded, skipped, errors
