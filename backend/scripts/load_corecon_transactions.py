"""Load all Corecon transaction-detail CSVs into ``corecon_transactions``.

Auto-discovers every file matching the pattern
``corecon_transactiondetailsapi_export*_by_TransactionSource_*.csv`` in the
given directory (default: the OneDrive "Database files" folder).

Usage from the ``backend`` directory:

    python scripts\\load_corecon_transactions.py
    python scripts\\load_corecon_transactions.py --dir "E:\\path\\to\\folder"
    python scripts\\load_corecon_transactions.py --csv "file1.csv" --csv "file2.csv"
    python scripts\\load_corecon_transactions.py --mode truncate
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = THIS_DIR.parent
for _p in (BACKEND_DIR, THIS_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from db_csv_paths import database_files_dir  # noqa: E402

from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

skip_startup_lead_bootstrap()

from sqlalchemy import func, text  # noqa: E402
from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: E402

from app import create_app  # noqa: E402
from app.corecon_ids import stable_active_project_external_id  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.corecon_transaction import CoreconTransaction  # noqa: E402

DEFAULT_DIR = str(database_files_dir())
FILE_GLOB = "corecon_transactiondetailsapi_export*_by_TransactionSource_*.csv"

DOTNET_MIN = "01/01/0001 00:00:00"
DATE_FORMATS = ("%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S")

CSV_TO_FIELD: dict[str, str] = {
    "Id": "corecon_id",
    "TransactionItemSource": "transaction_item_source",
    "TransactionSource": "transaction_source",
    "TransactionCategoryLevel1": "transaction_category_level_1",
    "TransactionCategoryLevel2": "transaction_category_level_2",
    "TransactionCategoryLevel3": "transaction_category_level_3",
    "ProjectId": "project_corecon_id",
    "ProjectNumber": "project_number",
    "ProjectTitle": "project_title",
    "ProjectPMContactName": "project_pm_contact_name",
    "ProjectBidContactName": "project_bid_contact_name",
    "ProjectSalesContactName": "project_sales_contact_name",
    "ProjectEstStartDateUtc": "project_est_start_date_utc",
    "ProjectEstFinishDateUtc": "project_est_finish_date_utc",
    "PrimeContractEstFinishDateInclCODaysUtc": "prime_contract_est_finish_date_incl_co_days_utc",
    "ProjectEstStartDateOrgLocal": "project_est_start_date_org_local",
    "ProjectEstFinishDateOrgLocal": "project_est_finish_date_org_local",
    "PrimeContractEstFinishDateInclCODaysOrgLocal": "prime_contract_est_finish_date_incl_co_days_org_local",
    "PrimeContractId": "prime_contract_corecon_id",
    "PrimeContractNumber": "prime_contract_number",
    "PrimeContractSubject": "prime_contract_subject",
    "PrimeContractBillingType": "prime_contract_billing_type",
    "PrimeContractBillingTypeValue": "prime_contract_billing_type_value",
    "PrimeContractIssueDateUtc": "prime_contract_issue_date_utc",
    "PrimeContractIssueDateOrgLocal": "prime_contract_issue_date_org_local",
    "PrimeContractApprovalDateUtc": "prime_contract_approval_date_utc",
    "PrimeContractApprovalDateOrgLocal": "prime_contract_approval_date_org_local",
    "OwnerCompanyName": "owner_company_name",
    "OwnerContact": "owner_contact",
    "PrimeCompanyName": "prime_company_name",
    "PrimeContact": "prime_contact",
    "PrimeContractStatus": "prime_contract_status",
    "PrimeContractEstStartDateUtc": "prime_contract_est_start_date_utc",
    "PrimeContractEstFinishDateUtc": "prime_contract_est_finish_date_utc",
    "PrimeContractEstStartDateOrgLocal": "prime_contract_est_start_date_org_local",
    "PrimeContractEstFinishDateOrgLocal": "prime_contract_est_finish_date_org_local",
    "PrimeContractChangeOrderImpactDays": "prime_contract_change_order_impact_days",
    "COId": "co_corecon_id",
    "CONumber": "co_number",
    "COSubject": "co_subject",
    "COIssueDateUtc": "co_issue_date_utc",
    "COIssueDateOrgLocal": "co_issue_date_org_local",
    "COStatusDateUtc": "co_status_date_utc",
    "COStatusDateOrgLocal": "co_status_date_org_local",
    "WorkOrderId": "work_order_corecon_id",
    "WorkOrderNumber": "work_order_number",
    "WorkOrderSubject": "work_order_subject",
    "WorkOrderIssueDateUtc": "work_order_issue_date_utc",
    "WorkOrderIssueDateOrgLocal": "work_order_issue_date_org_local",
    "WorkOrderStatusDateUtc": "work_order_status_date_utc",
    "WorkOrderStatusDateOrgLocal": "work_order_status_date_org_local",
    "JobCostCodeId": "job_cost_code_corecon_id",
    "JobCostCodeOrderNumber": "job_cost_code_order_number",
    "JobCostCode": "job_cost_code",
    "JobCostCodeDescription": "job_cost_code_description",
    "JobCostCodeQuantity": "job_cost_code_quantity",
    "JobCostCodeUnit": "job_cost_code_unit",
    "JobCostCodeInternalDivision": "job_cost_code_internal_division",
    "JobCostCodeInternalDivisionDesc": "job_cost_code_internal_division_desc",
    "JobCostCodeInternalMajor": "job_cost_code_internal_major",
    "JobCostCodeInternalMajorDesc": "job_cost_code_internal_major_desc",
    "JobCostCodeInternalMinor": "job_cost_code_internal_minor",
    "JobCostCodeInternalMinorDesc": "job_cost_code_internal_minor_desc",
    "JobCostCodeInternalSubMinor": "job_cost_code_internal_sub_minor",
    "JobCostCodeInternalSubMinorDesc": "job_cost_code_internal_sub_minor_desc",
    "OwnerCostCode": "owner_cost_code",
    "OwnerCostCodeDescription": "owner_cost_code_description",
    "TransactionId": "transaction_corecon_id",
    "TransactionNumber": "transaction_number",
    "TransactionSubject": "transaction_subject",
    "TransactionType": "transaction_type",
    "TransactionStatus": "transaction_status",
    "TransactionDateUtc": "transaction_date_utc",
    "TransactionDateOrgLocal": "transaction_date_org_local",
    "TransactionCompanyId": "transaction_company_corecon_id",
    "TransactionCompanyName": "transaction_company_name",
    "TransactionCompanyCode": "transaction_company_code",
    "TransactionContactId": "transaction_contact_corecon_id",
    "TransactionContact": "transaction_contact",
    "TransactionExportStatus": "transaction_export_status",
    "TransactionExportId": "transaction_export_id",
    "TransactionExportDateUtc": "transaction_export_date_utc",
    "TransactionExportDateOrgLocal": "transaction_export_date_org_local",
    "TransactionPaymentAmount": "transaction_payment_amount",
    "TransactionItemId": "transaction_item_corecon_id",
    "TransactionItemOrderNumber": "transaction_item_order_number",
    "TransactionItemDescription": "transaction_item_description",
    "TransactionItemQuantity": "transaction_item_quantity",
    "TransactionItemUnit": "transaction_item_unit",
    "TransactionItemUnitPrice": "transaction_item_unit_price",
    "TransactionItemUnitPrice2": "transaction_item_unit_price_2",
    "TransactionItemGrossTotal": "transaction_item_gross_total",
    "TransactionItemSubtotal": "transaction_item_subtotal",
    "TransactionItemSubtotal2": "transaction_item_subtotal_2",
    "TransactionItemTaxId": "transaction_item_tax_id",
    "TransactionItemTaxTotal": "transaction_item_tax_total",
    "TransactionItemTotal": "transaction_item_total",
    "TransactionItemInvoicedTotal": "transaction_item_invoiced_total",
    "TransactionInvoicedDateUtc": "transaction_invoiced_date_utc",
    "TransactionInvoicedDateOrgLocal": "transaction_invoiced_date_org_local",
    "TransactionItemResourceType": "transaction_item_resource_type",
    "TransactionItemBillableStatus": "transaction_item_billable_status",
    "TransactionStartDateUtc": "transaction_start_date_utc",
    "TransactionStartDateOrgLocal": "transaction_start_date_org_local",
    "TransactionFinishDateUtc": "transaction_finish_date_utc",
    "TransactionFinishDateOrgLocal": "transaction_finish_date_org_local",
    "TransactionProjectMultiplier": "transaction_project_multiplier",
    "TransactionOrgMultiplier": "transaction_org_multiplier",
    "TransactionItemCreatedUtc": "transaction_item_created_utc",
    "TransactionItemModifiedUtc": "transaction_item_modified_utc",
    "ActiveProjectExternalId": "active_project_external_id",
}

INT_FIELDS = {
    "project_corecon_id",
    "prime_contract_corecon_id",
    "prime_contract_change_order_impact_days",
    "co_corecon_id",
    "work_order_corecon_id",
    "job_cost_code_corecon_id",
    "transaction_corecon_id",
    "transaction_company_corecon_id",
    "transaction_contact_corecon_id",
    "transaction_item_corecon_id",
}

DECIMAL_FIELDS = {
    "job_cost_code_quantity",
    "transaction_payment_amount",
    "transaction_item_quantity",
    "transaction_item_unit_price",
    "transaction_item_unit_price_2",
    "transaction_item_gross_total",
    "transaction_item_subtotal",
    "transaction_item_subtotal_2",
    "transaction_item_tax_total",
    "transaction_item_total",
    "transaction_item_invoiced_total",
    "transaction_project_multiplier",
    "transaction_org_multiplier",
}

DATETIME_FIELDS = {f for f in CSV_TO_FIELD.values() if f.endswith("_utc") or f.endswith("_org_local")}


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    if v == "" or v == DOTNET_MIN:
        return None
    return v


def _to_int(value: str | None) -> int | None:
    v = _clean(value)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        try:
            return int(float(v))
        except ValueError:
            return None


def _to_decimal(value: str | None) -> Decimal | None:
    v = _clean(value)
    if v is None:
        return None
    try:
        return Decimal(v)
    except (InvalidOperation, ValueError):
        return None


def _to_datetime(value: str | None) -> datetime | None:
    v = _clean(value)
    if v is None:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def transform_row(row: dict[str, Any], source_file: str) -> dict[str, Any] | None:
    """Convert one raw CSV row into a dict ready for INSERT.

    Returns ``None`` if the row is missing the parts of the natural key.
    """
    out: dict[str, Any] = {"source_file": source_file, "raw_row": row}
    for csv_col, field in CSV_TO_FIELD.items():
        raw = row.get(csv_col)
        if field in INT_FIELDS:
            out[field] = _to_int(raw)
        elif field in DECIMAL_FIELDS:
            out[field] = _to_decimal(raw)
        elif field in DATETIME_FIELDS:
            out[field] = _to_datetime(raw)
        else:
            out[field] = _clean(raw)

    if not out.get("transaction_source"):
        return None
    if out.get("transaction_corecon_id") is None:
        return None
    if out.get("transaction_item_corecon_id") is None:
        return None

    apid = out.get("active_project_external_id")
    if apid is None or str(apid).strip() == "":
        out["active_project_external_id"] = stable_active_project_external_id(
            project_corecon_id=out.get("project_corecon_id"),
            project_number=out.get("project_number"),
        )
    return out


def discover_files(directory: str) -> list[Path]:
    return sorted(Path(directory).glob(FILE_GLOB))


def load_file(path: Path, mode: str, batch_size: int) -> tuple[int, int, int]:
    inserted = skipped = errors = 0
    pending: list[dict[str, Any]] = []
    source_file = path.name

    table = CoreconTransaction.__table__
    conflict_cols = ["transaction_source", "transaction_corecon_id", "transaction_item_corecon_id"]

    def flush() -> int:
        if not pending:
            return 0
        # Same-file duplicates can appear in Corecon exports; Postgres rejects
        # ``INSERT ... ON CONFLICT`` when the batch proposes the same conflict key twice.
        dedup: dict[tuple[Any, Any, Any], dict[str, Any]] = {}
        for p in pending:
            key = (
                p.get("transaction_source"),
                p.get("transaction_corecon_id"),
                p.get("transaction_item_corecon_id"),
            )
            dedup[key] = p
        rows = list(dedup.values())
        if mode == "truncate":
            stmt = pg_insert(table).values(rows)
        else:
            stmt = pg_insert(table).values(rows)
            # Do not overwrite ``project_id`` here; ``scripts/link_jobs.py`` sets it from ``project_number``.
            update_cols = {
                c.name: stmt.excluded[c.name]
                for c in table.columns
                if c.name not in {"id", "created_at", "project_id", *conflict_cols}
            }
            update_cols["updated_at"] = func.now()
            stmt = stmt.on_conflict_do_update(
                constraint="uq_corecon_transactions_source_txn_item",
                set_=update_cols,
            )
        db.session.execute(stmt)
        db.session.commit()
        return len(rows)

    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for line_no, row in enumerate(reader, start=2):
            try:
                payload = transform_row(row, source_file)
            except Exception as exc:  # pragma: no cover  (defensive)
                errors += 1
                print(f"  ! line {line_no}: {exc!r}", file=sys.stderr)
                continue
            if payload is None:
                skipped += 1
                continue
            pending.append(payload)
            if len(pending) >= batch_size:
                inserted += flush()
                pending.clear()
        inserted += flush()
        pending.clear()
    return inserted, skipped, errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=DEFAULT_DIR, help="Directory to glob for CSV files")
    parser.add_argument(
        "--csv",
        action="append",
        default=[],
        help="Explicit CSV file path (repeatable). Overrides --dir when given.",
    )
    parser.add_argument(
        "--mode",
        choices=("upsert", "truncate"),
        default="upsert",
        help="upsert: INSERT ... ON CONFLICT DO UPDATE per natural key. "
             "truncate: TRUNCATE the table first, then plain INSERT.",
    )
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()

    if args.csv:
        files = [Path(p) for p in args.csv]
    else:
        files = discover_files(args.dir)

    files = [p for p in files if p.is_file()]
    if not files:
        print(f"No matching CSV files found (looked in {args.dir!r}).", file=sys.stderr)
        return 2

    print(f"Found {len(files)} file(s):")
    for f in files:
        print(f"  {f.name}  ({f.stat().st_size:,} bytes)")
    print(f"Mode: {args.mode}")

    app = create_app()
    with app.app_context():
        if args.mode == "truncate":
            print("Truncating corecon_transactions ...")
            db.session.execute(text("TRUNCATE corecon_transactions RESTART IDENTITY;"))
            db.session.commit()

        grand_inserted = grand_skipped = grand_errors = 0
        for path in files:
            print(f"\n=> {path.name}")
            ins, skp, err = load_file(path, args.mode, args.batch_size)
            print(f"   inserted={ins}  skipped={skp}  errors={err}")
            grand_inserted += ins
            grand_skipped += skp
            grand_errors += err

        print(
            f"\nLoaded {grand_inserted} rows into corecon_transactions "
            f"(skipped {grand_skipped}, errors {grand_errors})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
