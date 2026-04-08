"""
Public whitelisted API for the Cashew Import workflow.

Endpoints:
  parse_and_preview(run_name)     — parse the uploaded CSV, apply mappings,
                                    save rows to the child table, return preview
  queue_run(run_name)             — validate at queue time, enqueue the worker
  get_run_progress(run_name)      — return live counters for the progress bar
"""

import frappe
from frappe import _
from frappe.utils import cint, flt

from cashew_integration.importer.parser import parse_csv
from cashew_integration.importer.mapping import apply_mappings
from cashew_integration.importer.validation import validate_run_config, validate_rows_at_queue_time
from cashew_integration.importer.idempotency import apply_idempotency_guard
from cashew_integration.importer.worker import enqueue_run


# ── parse + preview ────────────────────────────────────────────────────────────

@frappe.whitelist()
def parse_and_preview(run_name: str) -> dict:
    """
    1. Load the attached CSV from the run.
    2. Parse and normalise all rows.
    3. Apply account/category/exchange-rate/party mappings.
    4. Save rows to the Cashew Import Row child table.
    5. Update run counters and status → Validated.
    6. Return a summary dict suitable for the frontend preview.

    Permission: Accountant or System Manager.
    """
    run = frappe.get_doc("Cashew Import Run", run_name)
    frappe.has_permission("Cashew Import Run", doc=run, throw=True)

    if run.status not in ("Draft", "Validated"):
        frappe.throw(
            f"Cannot re-parse a run with status '{run.status}'. "
            "Only Draft or Validated runs can be re-parsed.",
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
    run.status = "Validated"
    run.save(ignore_permissions=False)
    frappe.db.commit()

    return {
        "status": "ok",
        "rows_total":  run.rows_total,
        "rows_valid":  run.rows_valid,
        "rows_failed": run.rows_failed,
        "run_status":  run.status,
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
    run.db_set("rows_skipped",
               sum(1 for r in rows if r.get("validation_status") == "Skipped"),
               notify=True)
    run.db_set("rows_failed",
               sum(1 for r in rows if r.get("validation_status") == "Error"),
               notify=True)
    frappe.db.commit()

    return {"status": "queued", "job_id": job_id, "rows_valid": valid_count}


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


# ── internal helpers ───────────────────────────────────────────────────────────

def _read_attached_file(file_url: str) -> bytes:
    if not file_url:
        frappe.throw("No source file is attached to this run.", frappe.ValidationError)
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    return file_doc.get_content()


def _dict_to_child(row: dict, child) -> None:
    """Copy flat row dict fields onto a child doc, skipping private keys."""
    skip = {"income_flag", "_note_type", "_transfer_source_name", "_transfer_dest_name"}
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
    d = {f: child_row.get(f) for f in fields}
    # income_flag is not stored on the child; re-derive from txn_type for
    # Transfer pair orientation (only needed if worker re-reads rows)
    return d
