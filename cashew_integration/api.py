"""
Public whitelisted API for the Cashew Import workflow.

Endpoints:
  parse_and_preview(run_name)     — parse the uploaded CSV, apply mappings,
                                    save rows to the child table, return preview
  validate_import(run_name)       — run strict validation on imported rows
  queue_run(run_name)             — validate at queue time, enqueue the worker
  cancel_run(run_name)            — cancel a queued/processing run
  revert_run(run_name)            — cancel all posted ERP docs for a completed run
  get_run_progress(run_name)      — return live counters for the progress bar
  setup_from_csv(company, file_url) — seed Cashew Settings from a Cashew CSV export
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, now

from cashew_integration.importer.parser import parse_csv
from cashew_integration.importer.mapping import apply_mappings, apply_exchange_rates
from cashew_integration.importer.validation import (
    validate_run_config,
    validate_rows_at_queue_time,
    get_run_config_errors,
)
from cashew_integration.importer.idempotency import apply_idempotency_guard
from cashew_integration.importer.worker import enqueue_run, enqueue_revert


# ── parse + preview ────────────────────────────────────────────────────────────

@frappe.whitelist()
def parse_and_preview(run_name: str) -> dict:
    """
    1. Load the attached CSV from the run.
    2. Parse and normalise all rows.
    3. Apply account/category/exchange-rate/party mappings.
    4. Save rows to the Cashew Import Row child table.
    5. Update run counters and status → Parsed.
    6. Return a summary dict suitable for the frontend preview.

    Permission: Accountant or System Manager.
    """
    run = frappe.get_doc("Cashew Import Run", run_name)
    frappe.has_permission("Cashew Import Run", doc=run, throw=True)

    if run.status not in ("Draft", "Parsed", "Validated"):
        frappe.throw(
            f"Cannot re-parse a run with status '{run.status}'. "
            "Only Draft, Parsed, or Validated runs can be re-parsed.",
            frappe.PermissionError,
        )

    # Load the file bytes
    file_content = _read_attached_file(run.source_file)

    company_currency = frappe.get_cached_value("Company", run.company, "default_currency")

    # Parse
    rows = parse_csv(file_content, company_currency)

    # Map
    apply_mappings(rows, run)
    # Persist rows to child table (replace existing)
    run.set("import_rows", [])
    for row in rows:
        child = run.append("import_rows", {})
        _dict_to_child(row, child)

    run.rows_total = len(rows)
    run.rows_valid = sum(1 for r in rows if r.get("validation_status") == "Valid")
    run.rows_failed = sum(1 for r in rows if r.get("validation_status") == "Error")
    run.rows_skipped = 0
    run.rows_posted = 0
    run.status = "Parsed"
    run.save(ignore_permissions=False)
    frappe.db.commit()

    return {
        "status": "ok",
        "rows_total":  run.rows_total,
        "rows_valid":  run.rows_valid,
        "rows_failed": run.rows_failed,
        "run_status":  run.status,
        "run_config_errors": [],
    }


@frappe.whitelist()
def validate_import(run_name: str) -> dict:
    """
    Run strict validation on imported rows.

    - If all checks pass, status transitions Parsed -> Validated.
    - If row/config errors exist, status remains Parsed and details are returned.
    """
    run = frappe.get_doc("Cashew Import Run", run_name)
    frappe.has_permission("Cashew Import Run", doc=run, throw=True)

    if run.status not in ("Parsed", "Validated"):
        frappe.throw(
            f"Run must be in Parsed or Validated status to validate "
            f"(current: '{run.status}').",
            frappe.ValidationError,
        )

    rows = [_child_to_dict(r) for r in run.import_rows]

    # Reset queue-time errors so re-validation sees the current state of each row.
    # Parse-stage errors (account not mapped, wrong file type) are permanent and kept.
    # Everything else must be re-evaluated — the user may have fixed the issue
    # (e.g. set a party, added a currency exchange record) since the last validate.
    _PARSE_STAGE_ERRORS = {
        "CASHEW_ACCOUNT_NOT_MAPPED",
        "EXTERNAL_ACCOUNT_NOT_MAPPED",
        "FILE_WRONG_EXPORT_TYPE",
        "FILE_MISSING_COLUMNS",
    }
    for row in rows:
        if (row.get("validation_status") == "Error"
                and row.get("validation_error_code") not in _PARSE_STAGE_ERRORS):
            row["validation_status"] = "Valid"
            row["validation_error_code"] = None
            row["validation_error_message"] = None

    # Step 1: Fetch exchange rates (ERP local → online providers).
    # This is the deliberate trigger point — rates are fetched only when the
    # user clicks Validate Import, not at parse time.
    company_currency = frappe.get_cached_value("Company", run.company, "default_currency")
    fx_summary = apply_exchange_rates(rows, company_currency)

    # Step 2: Strict row validation (uses freshly filled rates).
    validate_rows_at_queue_time(rows)

    # Step 3: Idempotency pre-check — surface duplicates before the user queues
    # so they can review or abort without any rows touching the ERP.
    # Worker re-runs this at post time for race-condition safety.
    apply_idempotency_guard(rows, run)

    run_config_errors = get_run_config_errors(run, rows)

    for row in rows:
        frappe.db.set_value(
            "Cashew Import Row",
            {"parent": run.name, "row_idx": row["row_idx"]},
            {
                "validation_status":        row.get("validation_status"),
                "validation_error_code":    row.get("validation_error_code"),
                "validation_error_message": row.get("validation_error_message"),
                "exchange_rate":            row.get("exchange_rate"),
                "base_amount":              row.get("base_amount"),
                "is_duplicate":             row.get("is_duplicate", 0),
                "posted_doctype":           row.get("posted_doctype"),
                "posted_docname":           row.get("posted_docname"),
            },
        )

    valid_count = sum(1 for r in rows if r.get("validation_status") == "Valid")
    failed_count = sum(1 for r in rows if r.get("validation_status") == "Error")
    skipped_count = sum(1 for r in rows if r.get("validation_status") == "Skipped")
    error_code_counts = _count_error_codes(rows)
    fx_error_count = sum(
        error_code_counts.get(code, 0)
        for code in ("EXCHANGE_RATE_MISSING", "EXCHANGE_RATE_INVALID")
    )

    run.db_set("rows_valid", valid_count, notify=True)
    run.db_set("rows_failed", failed_count, notify=True)
    run.db_set("rows_skipped", skipped_count, notify=True)

    if failed_count == 0 and not run_config_errors:
        run.db_set("status", "Validated", notify=True)
        frappe.db.commit()
        return {
            "status": "validated",
            "run_status": "Validated",
            "rows_valid": valid_count,
            "rows_failed": failed_count,
            "error_code_counts": error_code_counts,
            "fx_error_count": fx_error_count,
            "fx_summary": fx_summary,
            "run_config_errors": [],
        }

    run.db_set("status", "Parsed", notify=True)
    frappe.db.commit()
    return {
        "status": "invalid",
        "run_status": "Parsed",
        "rows_valid": valid_count,
        "rows_failed": failed_count,
        "error_code_counts": error_code_counts,
        "fx_error_count": fx_error_count,
        "fx_summary": fx_summary,
        "run_config_errors": run_config_errors,
    }


# ── queue run ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def queue_run(run_name: str) -> dict:
    """
    Run queue-time validation and enqueue the async worker.

    Raises ValidationError with a structured message if config is missing or
    all rows are blocked.  On success sets run.status = Queued and returns
    the job ID.

    Permission: Accountant or System Manager.
    """
    run = frappe.get_doc("Cashew Import Run", run_name)
    frappe.has_permission("Cashew Import Run", doc=run, throw=True)

    if run.status != "Validated":
        frappe.throw(
            f"Run must be in Validated status to queue (current: '{run.status}').",
            frappe.ValidationError,
        )

    rows = [_child_to_dict(r) for r in run.import_rows]

    # Queue-time validation
    validate_run_config(run, rows)
    validate_rows_at_queue_time(rows)

    # Idempotency pre-check
    apply_idempotency_guard(rows, run)

    # Persist queue-time validation results back to rows
    for row in rows:
        frappe.db.set_value(
            "Cashew Import Row",
            {"parent": run.name, "row_idx": row["row_idx"]},
            {
                "validation_status":        row.get("validation_status"),
                "validation_error_code":    row.get("validation_error_code"),
                "validation_error_message": row.get("validation_error_message"),
                "is_duplicate":             row.get("is_duplicate", 0),
                "posted_doctype":           row.get("posted_doctype"),
                "posted_docname":           row.get("posted_docname"),
            },
        )

    valid_count = sum(1 for r in rows if r.get("validation_status") == "Valid")
    failed_count = sum(1 for r in rows if r.get("validation_status") == "Error")
    skipped_count = sum(1 for r in rows if r.get("validation_status") == "Skipped")

    if failed_count > 0:
        frappe.throw(
            f"Import is blocked: {failed_count} row(s) still have errors after queue-time "
            "validation. Fix all errored rows before queueing.",
            frappe.ValidationError,
            title="RUN_BLOCKED_BY_ROW_ERRORS",
        )

    if valid_count == 0:
        frappe.throw(
            "No valid rows to import after queue-time validation. "
            "Check the row-level errors before retrying.",
            frappe.ValidationError,
        )

    job_id = enqueue_run(run_name)
    run.db_set("status",         "Queued",  notify=True)
    run.db_set("queued_job_id",  job_id,    notify=True)
    run.db_set("rows_valid",     valid_count, notify=True)
    run.db_set("rows_skipped",   skipped_count, notify=True)
    run.db_set("rows_failed",    failed_count,  notify=True)
    frappe.db.commit()

    return {"status": "queued", "job_id": job_id, "rows_valid": valid_count}


@frappe.whitelist()
def revert_run(run_name: str) -> dict:
    """
    Cancel all posted ERP documents for a completed or partially-posted run.

    Allowed on: Completed, Failed, Cancelled, Revert-Failed.
    Sets status → Reverting and enqueues the async revert worker.
    The worker cancels each posted SI/PI/JE and tracks per-row revert status.

    Permission: Accountant or System Manager.
    """
    run = frappe.get_doc("Cashew Import Run", run_name)
    frappe.has_permission("Cashew Import Run", doc=run, throw=True)

    if run.status not in ("Completed", "Failed", "Cancelled", "Revert-Failed"):
        frappe.throw(
            f"Only Completed, Failed, Cancelled, or Revert-Failed runs can be reverted "
            f"(current: '{run.status}').",
            frappe.ValidationError,
        )

    job_id = enqueue_revert(run_name)
    run.db_set("status", "Reverting", notify=True)
    frappe.db.commit()

    return {"status": "reverting", "job_id": job_id}


@frappe.whitelist()
def cancel_run(run_name: str) -> dict:
    """
    Cancel a queued/processing run.

    - If status is Queued, it is marked Cancelled immediately.
    - If status is Processing, worker loop will stop on next cancellation check.
    """
    run = frappe.get_doc("Cashew Import Run", run_name)
    frappe.has_permission("Cashew Import Run", doc=run, throw=True)

    if run.status not in ("Queued", "Processing"):
        frappe.throw(
            f"Only Queued or Processing runs can be cancelled (current: '{run.status}').",
            frappe.ValidationError,
        )

    run.db_set("status", "Cancelled", notify=True)
    run.db_set("finished_on", str(run.finished_on or now()), notify=True)
    frappe.db.commit()
    return {"status": "cancelled", "run_status": "Cancelled"}


# ── progress polling ───────────────────────────────────────────────────────────

@frappe.whitelist()
def get_run_progress(run_name: str) -> dict:
    """
    Return lightweight counters for frontend progress polling.
    Permission: Accountant or System Manager (read access suffices).
    """
    run = frappe.get_doc("Cashew Import Run", run_name)
    frappe.has_permission("Cashew Import Run", doc=run, throw=True)

    return {
        "status":       run.status,
        "rows_total":   run.rows_total or 0,
        "rows_posted":  run.rows_posted or 0,
        "rows_failed":  run.rows_failed or 0,
        "rows_skipped": run.rows_skipped or 0,
        "rows_valid":   run.rows_valid or 0,
        "started_on":   str(run.started_on or ""),
        "finished_on":  str(run.finished_on or ""),
        "diagnostics_file": run.diagnostics_file or "",
    }


# ── setup wizard ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def setup_from_csv(file_url: str, company: str | None = None) -> dict:
    """
    Seed Cashew Settings from a Cashew CSV export file.

    Finds or creates Chart of Accounts entries for each category and cashew
    account found in the CSV, then populates the account/category mapping
    tables in Cashew Settings.  Already-mapped entries are skipped.

    Permission: System Manager only.
    """
    frappe.only_for("System Manager")

    from cashew_integration.setup import run_setup_from_csv
    csv_bytes = _read_attached_file(file_url)
    return run_setup_from_csv(company, csv_bytes)


# ── internal helpers ───────────────────────────────────────────────────────────

def _read_attached_file(file_url: str) -> bytes:
    if not file_url:
        frappe.throw("No source file is attached to this run.", frappe.ValidationError)
    # Use get_full_path() + raw read to avoid get_content()'s encode/decode
    # chain (Frappe 16 decodes through FILE_ENCODING_OPTIONS before returning,
    # which can corrupt non-ASCII content when re-encoded).  The parser's own
    # _decode() handles UTF-8 / UTF-8-BOM detection from raw bytes.
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    file_path = file_doc.get_full_path()
    with open(file_path, "rb") as f:
        content = f.read()
    return content


def _dict_to_child(row: dict, child) -> None:
    """Copy flat row dict fields onto a child doc, skipping private keys."""
    skip = {"_note_type", "_transfer_source_name", "_transfer_dest_name"}
    for k, v in row.items():
        if k.startswith("_") or k in skip:
            continue
        try:
            child.set(k, v)
        except Exception:
            pass


def _child_to_dict(child_row) -> dict:
    """Convert a child doc to a plain dict for the validation/idempotency engines."""
    fields = [f.fieldname for f in child_row.meta.fields]
    return {f: child_row.get(f) for f in fields}


def _count_error_codes(rows: list[dict]) -> dict:
    counts = {}
    for row in rows:
        if row.get("validation_status") != "Error":
            continue
        code = row.get("validation_error_code") or "UNKNOWN_ERROR"
        counts[code] = counts.get(code, 0) + 1
    return counts
