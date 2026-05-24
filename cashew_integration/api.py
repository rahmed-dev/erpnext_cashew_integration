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

from cashew_integration.importer.parser import parse_csv, _assign_txn_type
from cashew_integration.importer.category_lookup import build_category_type_map
from cashew_integration.importer.mapping import apply_mappings, apply_exchange_rates
from cashew_integration.importer.validation import (
    validate_run_config,
    validate_rows_at_queue_time,
    get_run_config_errors,
    validate_party_present,
    check_category_account_class,
)
from cashew_integration.importer.idempotency import apply_idempotency_guard
from cashew_integration.importer.realtime import emit_row_update_batch
from cashew_integration.importer.worker import enqueue_run, enqueue_revert


_REALTIME_ROW_PATCH_FIELDS = (
    "validation_status", "validation_error_code", "validation_error_message",
    "posted_doctype", "posted_docname", "posted_gl_date",
    "is_duplicate", "exchange_rate", "base_amount",
    "transfer_pair_row_idx", "resolved_party", "resolved_party_type",
    "party_source", "resolved_route", "resolved_account",
    "resolved_external_account", "revert_status", "revert_error",
    "txn_type", "requires_party",
)


def _row_patch(row) -> dict:
    """Build a compact realtime patch dict from a row dict or child doc."""
    if isinstance(row, dict):
        get = row.get
    else:
        get = row.get  # frappe child docs also expose .get(fieldname)
    patch = {"row_idx": get("row_idx")}
    for field in _REALTIME_ROW_PATCH_FIELDS:
        value = get(field)
        if value is not None:
            patch[field] = value
    return patch


# ── row-explorer mutation gating ───────────────────────────────────────────────

_ROW_EXPLORER_MUTATION_ALLOWED_STATUSES = {
    "Draft", "Parsed", "Validated", "Failed", "Cancelled", "Revert-Failed",
}


def _coerce_row_indices(value):
    """Frappe routes list/dict args through ``frappe.form_dict`` which JSON-
    encodes them — the handler receives a string like ``"[1,2,3]"`` or
    ``"null"`` rather than a Python list / None. Normalize to a list of ints
    or None.
    """
    import json as _json
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if not s or s.lower() == "null":
            return None
        try:
            value = _json.loads(s)
        except Exception:
            frappe.throw(_("row_indices must be a JSON array of integers."))
    if isinstance(value, (list, tuple, set)):
        return [int(i) for i in value]
    frappe.throw(_("row_indices must be a JSON array of integers."))


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
    run.period_start, run.period_end = _compute_txn_period(rows)
    run.status = "Parsed"
    run.save(ignore_permissions=False)
    frappe.db.commit()

    return {
        "status": "ok",
        "rows_total":  run.rows_total,
        "rows_valid":  run.rows_valid,
        "rows_failed": run.rows_failed,
        "period_start": run.period_start,
        "period_end":   run.period_end,
        "run_status":  run.status,
        "run_config_errors": [],
    }


def _compute_txn_period(rows: list[dict]) -> tuple[str | None, str | None]:
    dates = [r["txn_date"] for r in rows if r.get("txn_date")]
    if not dates:
        return None, None
    return min(dates), max(dates)


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

    # Step 0 (f006 c002 option-b): re-apply txn_type AND re-resolve
    # resolved_account from the current Cashew Category Mapping. Captures
    # mapping edits (category_type, default_account, requires_party) made
    # between parse and validate without requiring a CSV re-upload. Skips
    # Error rows + Transfer-family rows that already went through
    # _classify_transfer_rows at parse time.
    category_map = build_category_type_map()
    for row in rows:
        if row.get("validation_status") == "Error":
            continue
        if row.get("txn_type") in ("Transfer", "External Transfer", "Adjustment"):
            continue
        _assign_txn_type(row, category_map)
        cat = (
            category_map.get((row.get("category"), row.get("sub_category") or ""))
            or category_map.get((row.get("category"), ""))
        )
        if cat:
            row["resolved_account"] = cat.get("default_account")
            row["requires_party"]   = 1 if cat.get("requires_party") else 0

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
                # f006 c002 option-b — persist re-evaluated routing + mapping.
                "txn_type":                 row.get("txn_type"),
                "resolved_route":           row.get("resolved_route"),
                "resolved_account":         row.get("resolved_account"),
                "requires_party":           row.get("requires_party", 0),
            },
        )
    emit_row_update_batch(run.name, [_row_patch(r) for r in rows])

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
    emit_row_update_batch(run.name, [_row_patch(r) for r in rows])

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
    frappe.has_permission("Cashew Import Run", ptype="read", doc=run, throw=True)

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
    frappe.has_permission("Cashew Import Run", ptype="create", throw=True)
    if company:
        frappe.has_permission("Company", ptype="read", doc=company, throw=True)
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


# ── f006 c006 — Row Explorer API ───────────────────────────────────────────────

_ROW_EXPLORER_FIELDS = (
    "row_idx", "txn_date", "raw_amount", "source_currency", "company_currency",
    "exchange_rate", "base_amount", "income_flag", "txn_type", "category",
    "sub_category", "title", "note", "raw_account", "resolved_route",
    "requires_party", "resolved_account", "resolved_erp_account",
    "resolved_external_account", "resolved_party_type", "resolved_party",
    "validation_status", "validation_error_code", "validation_error_message",
    "posted_doctype", "posted_docname", "posted_gl_date", "is_duplicate",
    "revert_status", "revert_error",
)


@frappe.whitelist()
def row_explorer_load(run_name: str) -> dict:
    """Read-only payload for the Cashew Row Explorer Vue page.

    Returns rows + run-level counters + a ``mutation_allowed`` gate the UI uses
    to enable / disable inline edits.
    """
    run = frappe.get_doc("Cashew Import Run", run_name)
    frappe.has_permission("Cashew Import Run", ptype="read", doc=run, throw=True)

    rows = [
        {f: r.get(f) for f in _ROW_EXPLORER_FIELDS}
        for r in run.import_rows
    ]

    return {
        "run_name":          run.name,
        "status":            run.status,
        "company":           run.company,
        "company_currency":  frappe.get_cached_value("Company", run.company, "default_currency"),
        "rows_total":        run.rows_total,
        "rows_valid":        run.rows_valid,
        "rows_posted":       run.rows_posted,
        "rows_failed":       run.rows_failed,
        "rows_skipped":      run.rows_skipped,
        "mutation_allowed":  run.status in _ROW_EXPLORER_MUTATION_ALLOWED_STATUSES,
        "rows":              rows,
        "enums": {
            "txn_type":          ["Income", "Expense", "Transfer", "External Transfer",
                                  "Adjustment", "Loan Receivable", "Loan Payable"],
            "validation_status": ["", "Valid", "Error", "Skipped"],
        },
    }


@frappe.whitelist()
def row_explorer_set_party(
    run_name: str,
    row_indices,
    party_type: str,
    party: str,
) -> dict:
    """Set ``resolved_party`` + ``resolved_party_type`` on the given row_idxs
    and re-evaluate party-presence validation. Returns the updated row payloads
    so the UI can patch local state without a full reload.
    """
    run = frappe.get_doc("Cashew Import Run", run_name)
    frappe.has_permission("Cashew Import Run", ptype="write", doc=run, throw=True)

    if run.status not in _ROW_EXPLORER_MUTATION_ALLOWED_STATUSES:
        frappe.throw(_("Cannot edit rows when run status is {0}.").format(run.status))
    if party_type not in ("Customer", "Supplier"):
        frappe.throw(_("party_type must be Customer or Supplier."))
    if not party or not frappe.db.exists(party_type, party):
        frappe.throw(_("{0} '{1}' does not exist.").format(party_type, party))

    parsed = _coerce_row_indices(row_indices) or []
    target = set(parsed)
    if not target:
        frappe.throw(_("row_indices must not be empty."))

    updated = []
    for r in run.import_rows:
        if r.row_idx not in target:
            continue
        if r.posted_docname or r.revert_status == "Reverted":
            continue  # posted / reverted rows are read-only
        r.resolved_party_type = party_type
        r.resolved_party      = party
        # Clear any prior party-missing error before re-evaluating
        if r.validation_error_code in ("LOAN_PARTY_MISSING", "PARTY_MISSING"):
            r.validation_status        = "Valid"
            r.validation_error_code    = None
            r.validation_error_message = None
        # Re-run party-presence check (no-op when party now set; sets Error if not)
        row_dict = _child_to_dict(r)
        validate_party_present(row_dict)
        for k in ("validation_status", "validation_error_code", "validation_error_message"):
            r.set(k, row_dict.get(k))
        updated.append({f: r.get(f) for f in _ROW_EXPLORER_FIELDS})

    run.save(ignore_permissions=False)
    frappe.db.commit()
    emit_row_update_batch(run.name, [_row_patch(r) for r in updated])
    return {"updated": updated}


@frappe.whitelist()
def row_explorer_revalidate(
    run_name: str,
    row_indices=None,
) -> dict:
    """Re-run c002 routing + c003 party-presence validation against current
    Cashew Settings. If ``row_indices`` is None, revalidates all non-Skipped,
    non-Posted rows.
    """
    run = frappe.get_doc("Cashew Import Run", run_name)
    frappe.has_permission("Cashew Import Run", ptype="write", doc=run, throw=True)

    if run.status not in _ROW_EXPLORER_MUTATION_ALLOWED_STATUSES:
        frappe.throw(_("Cannot revalidate when run status is {0}.").format(run.status))

    cat_map = build_category_type_map()
    parsed = _coerce_row_indices(row_indices)
    target = set(parsed) if parsed is not None else None

    revalidated = []
    for r in run.import_rows:
        if target is not None and r.row_idx not in target:
            continue
        if r.posted_docname or r.validation_status == "Skipped":
            continue

        row_dict = _child_to_dict(r)
        # Reset prior validation state before re-evaluation
        row_dict["validation_status"]        = ""
        row_dict["validation_error_code"]    = None
        row_dict["validation_error_message"] = None
        # c002: re-route txn_type from current category_type
        _assign_txn_type(row_dict, cat_map)
        # c003: re-check party requirement
        validate_party_present(row_dict)
        # c001: account-class predicate (only when route present + non-transfer)
        if row_dict.get("txn_type") not in ("Transfer", "External Transfer", "Adjustment"):
            mapping_hit = cat_map.get(
                (row_dict.get("category"), row_dict.get("sub_category") or "")
            ) or cat_map.get((row_dict.get("category"), ""))
            if mapping_hit:
                msg = check_category_account_class(
                    mapping_hit.get("category_type"),
                    row_dict.get("resolved_account") or mapping_hit.get("default_account"),
                )
                if msg and row_dict.get("validation_status") != "Error":
                    from cashew_integration.importer.errors import set_row_validation_error
                    set_row_validation_error(row_dict, "CATEGORY_ACCOUNT_CLASS_MISMATCH", msg)

        # If no validator fired, the row is clean — stamp Valid so the UI pill
        # doesn't show "Pending" for re-validated rows that previously read Valid.
        if not row_dict.get("validation_status"):
            row_dict["validation_status"] = "Valid"
        for k in ("txn_type", "resolved_route",
                  "validation_status", "validation_error_code", "validation_error_message"):
            r.set(k, row_dict.get(k))
        revalidated.append({f: r.get(f) for f in _ROW_EXPLORER_FIELDS})

    run.save(ignore_permissions=False)
    frappe.db.commit()
    emit_row_update_batch(run.name, [_row_patch(r) for r in revalidated])
    return {"revalidated": revalidated}


# ---------------------------------------------------------------------------
# c009 — Finance Dashboard summary (D5 rule 4, D9 GL-derived).
# Sole consumer: SPA Finance Dashboard (c007). Read-only; idempotent.
# ---------------------------------------------------------------------------

@frappe.whitelist()
def dashboard_summary(
    period_start: str | None = None,
    period_end: str | None = None,
    company: str | None = None,
) -> dict:
    """Headline numbers for the SPA landing dashboard for a (period, company)."""
    if not period_start or not period_end:
        frappe.throw(_("period_start and period_end are required"))
    if not company:
        company = frappe.defaults.get_user_default("Company")
    if not company:
        frappe.throw(_("company is required"))

    frappe.has_permission("GL Entry", "read", throw=True)
    frappe.has_permission("Account", "read", throw=True)
    frappe.has_permission("Company", "read", doc=company, throw=True)

    currency = frappe.db.get_value("Company", company, "default_currency") or "PKR"

    income_total, expense_total, income_cats, expense_cats = _period_pnl(
        company, period_start, period_end
    )

    balance_tiles = _balance_tiles(
        company, period_start, period_end, income_total - expense_total
    )

    assets_by_account = _top_assets(company, period_end, n=10)

    recent_runs = _recent_runs(company)

    return {
        "period": {"start": period_start, "end": period_end},
        "company": company,
        "currency": currency,
        "income_total": _r(income_total),
        "expense_total": _r(expense_total),
        "income_by_account": income_cats,
        "expense_by_account": expense_cats,
        "assets_by_account": assets_by_account,
        "balance_tiles": balance_tiles,
        "recent_runs": recent_runs,
    }


def _r(x: float) -> float:
    return round(float(x or 0.0), 2)


def _period_pnl(company: str, start: str, end: str):
    """Returns (income_total, expense_total, top_income_accounts, top_expense_accounts).

    Breakdown buckets by Chart-of-Accounts `account_name` — GL Entry's
    `account` Link → Account.account_name. Falls back to the account
    name field when account_name is empty.
    """
    gl = frappe.qb.DocType("GL Entry")
    acc = frappe.qb.DocType("Account")
    pnl_rows = (
        frappe.qb.from_(gl)
        .inner_join(acc).on(gl.account == acc.name)
        .select(
            gl.account, acc.account_name, acc.root_type,
            gl.debit, gl.credit,
        )
        .where(
            (gl.company == company)
            & (gl.posting_date[start:end])
            & (gl.is_cancelled == 0)
            & (acc.root_type.isin(["Income", "Expense"]))
        )
    ).run(as_dict=True)

    income_total = 0.0
    expense_total = 0.0
    income_by_acc: dict[str, float] = {}
    expense_by_acc: dict[str, float] = {}

    for r in pnl_rows:
        label = r.account_name or r.account or "(Uncategorized)"
        if r.root_type == "Income":
            amt = (r.credit or 0.0) - (r.debit or 0.0)
            if amt <= 0:
                continue
            income_total += amt
            income_by_acc[label] = income_by_acc.get(label, 0.0) + amt
        else:
            amt = (r.debit or 0.0) - (r.credit or 0.0)
            if amt <= 0:
                continue
            expense_total += amt
            expense_by_acc[label] = expense_by_acc.get(label, 0.0) + amt

    return (
        income_total,
        expense_total,
        _top_n_with_other(income_by_acc, 10),
        _top_n_with_other(expense_by_acc, 10),
    )


def _top_n_with_other(by_label: dict, n: int) -> list[dict]:
    items = sorted(by_label.items(), key=lambda kv: kv[1], reverse=True)
    head = items[:n]
    tail = items[n:]
    out = [{"account": c, "amount": _r(a)} for c, a in head]
    if tail:
        other_amt = sum(a for _, a in tail)
        out.append({"account": "(Other)", "amount": _r(other_amt)})
    return out


def _balance_tiles(company: str, period_start: str, period_end: str,
                   net_for_period: float) -> dict:
    prior_end = _date_minus_1(period_start)

    def _balance(account_filters: dict, as_of: str) -> float:
        gl = frappe.qb.DocType("GL Entry")
        acc = frappe.qb.DocType("Account")
        rows = (
            frappe.qb.from_(gl)
            .inner_join(acc).on(gl.account == acc.name)
            .select(acc.root_type, gl.debit, gl.credit)
            .where(
                (gl.company == company)
                & (gl.posting_date <= as_of)
                & (gl.is_cancelled == 0)
                & _account_qb_filter(acc, account_filters)
            )
        ).run(as_dict=True)
        total = 0.0
        for r in rows:
            if r.root_type == "Asset":
                total += (r.debit or 0.0) - (r.credit or 0.0)
            else:
                total += (r.credit or 0.0) - (r.debit or 0.0)
        return total

    cash_bank_amount  = _balance({"account_type": ["in", ["Bank", "Cash"]]}, period_end)
    cash_bank_prior   = _balance({"account_type": ["in", ["Bank", "Cash"]]}, prior_end) if prior_end else None
    receivable_amount = _balance({"account_type": "Receivable"}, period_end)
    receivable_prior  = _balance({"account_type": "Receivable"}, prior_end) if prior_end else None
    payable_amount    = _balance({"account_type": "Payable"}, period_end)
    payable_prior     = _balance({"account_type": "Payable"}, prior_end) if prior_end else None

    return {
        "cash_bank":      {"amount": _r(cash_bank_amount),
                           "prior_amount": _r(cash_bank_prior) if cash_bank_prior is not None else None},
        "receivable":     {"amount": _r(receivable_amount),
                           "prior_amount": _r(receivable_prior) if receivable_prior is not None else None},
        "payable":        {"amount": _r(payable_amount),
                           "prior_amount": _r(payable_prior) if payable_prior is not None else None},
        "net_for_period": {"amount": _r(net_for_period)},
    }


def _date_minus_1(date_str: str) -> str | None:
    from datetime import datetime, timedelta
    if not date_str:
        return None
    return (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")


def _top_assets(company: str, as_of: str, n: int = 10) -> list[dict]:
    """Top Asset accounts by absolute closing balance as of `as_of`.

    Each row reports balance in its own account currency AND the equivalent
    in the company's base currency (so cross-currency sort / totalling is
    meaningful). Sort key = abs(base_amount).
    """
    company_currency = frappe.db.get_value("Company", company, "default_currency") or ""
    gl = frappe.qb.DocType("GL Entry")
    acc = frappe.qb.DocType("Account")
    rows = (
        frappe.qb.from_(gl)
        .inner_join(acc).on(gl.account == acc.name)
        .select(
            gl.account, acc.account_name, acc.account_currency,
            gl.debit_in_account_currency, gl.credit_in_account_currency,
            gl.debit, gl.credit,
        )
        .where(
            (gl.company == company)
            & (gl.posting_date <= as_of)
            & (gl.is_cancelled == 0)
            & (acc.root_type == "Asset")
        )
    ).run(as_dict=True)

    by_acc: dict = {}
    for r in rows:
        key = (r.account, r.account_name or r.account, r.account_currency or company_currency)
        acct_delta = (r.debit_in_account_currency or 0.0) - (r.credit_in_account_currency or 0.0)
        base_delta = (r.debit or 0.0) - (r.credit or 0.0)
        agg = by_acc.get(key, (0.0, 0.0))
        by_acc[key] = (agg[0] + acct_delta, agg[1] + base_delta)

    items = [
        {
            "account": name,
            "amount": _r(acct_bal),
            "currency": curr,
            "base_amount": _r(base_bal),
            "base_currency": company_currency,
        }
        for (_acc, name, curr), (acct_bal, base_bal) in by_acc.items()
        if abs(base_bal) > 0.005
    ]
    items.sort(key=lambda x: abs(x["base_amount"]), reverse=True)
    return items[:n]


@frappe.whitelist()
def balance_tile_detail(
    company: str | None = None,
    tile: str | None = None,
    as_of: str | None = None,
) -> dict:
    """Drill-down for Cash/Bank, Receivable, Payable balance tiles.

    - `cash_bank`  → list of accounts (account_type Cash or Bank) with closing balance
    - `receivable` → list of {party_type, party, balance} for Receivable accounts
    - `payable`    → same shape, sign flipped (open payables shown positive)

    All balances returned in each account's own currency.
    """
    if not company or not tile:
        frappe.throw(_("company and tile are required"))
    if tile not in ("cash_bank", "receivable", "payable"):
        frappe.throw(_("invalid tile id"))
    if not as_of:
        as_of = frappe.utils.today()

    frappe.has_permission("GL Entry", "read", throw=True)
    frappe.has_permission("Account", "read", throw=True)
    frappe.has_permission("Company", "read", doc=company, throw=True)

    company_currency = frappe.db.get_value("Company", company, "default_currency") or "PKR"

    if tile == "cash_bank":
        items = _detail_cash_bank(company, as_of, company_currency)
    else:
        account_type = "Receivable" if tile == "receivable" else "Payable"
        items = _detail_party_balance(company, as_of, account_type, company_currency)

    return {
        "tile": tile,
        "as_of": as_of,
        "company": company,
        "company_currency": company_currency,
        "items": items,
    }


def _detail_cash_bank(company: str, as_of: str, company_currency: str) -> list[dict]:
    gl = frappe.qb.DocType("GL Entry")
    acc = frappe.qb.DocType("Account")
    rows = (
        frappe.qb.from_(gl)
        .inner_join(acc).on(gl.account == acc.name)
        .select(
            gl.account, acc.account_name, acc.account_currency, acc.account_type,
            gl.debit_in_account_currency, gl.credit_in_account_currency,
            gl.debit, gl.credit,
        )
        .where(
            (gl.company == company)
            & (gl.posting_date <= as_of)
            & (gl.is_cancelled == 0)
            & (acc.account_type.isin(["Bank", "Cash"]))
        )
    ).run(as_dict=True)

    by_acc: dict = {}
    for r in rows:
        key = (r.account, r.account_name or r.account, r.account_currency or company_currency, r.account_type)
        acct_delta = (r.debit_in_account_currency or 0.0) - (r.credit_in_account_currency or 0.0)
        base_delta = (r.debit or 0.0) - (r.credit or 0.0)
        agg = by_acc.get(key, (0.0, 0.0))
        by_acc[key] = (agg[0] + acct_delta, agg[1] + base_delta)

    items = [
        {
            "account": name,
            "account_type": atype,
            "balance": _r(acct_bal),
            "currency": curr,
            "base_balance": _r(base_bal),
            "base_currency": company_currency,
        }
        for (_acc, name, curr, atype), (acct_bal, base_bal) in by_acc.items()
        if abs(base_bal) > 0.005
    ]
    items.sort(key=lambda x: abs(x["base_balance"]), reverse=True)
    return items


def _detail_party_balance(company: str, as_of: str, account_type: str,
                          company_currency: str) -> list[dict]:
    """Group open balances by party. Receivable = positive when customer owes you,
    Payable = positive when you owe the supplier."""
    sign = 1 if account_type == "Receivable" else -1

    gl = frappe.qb.DocType("GL Entry")
    acc = frappe.qb.DocType("Account")
    rows = (
        frappe.qb.from_(gl)
        .inner_join(acc).on(gl.account == acc.name)
        .select(
            gl.party_type, gl.party, gl.account, acc.account_currency,
            gl.debit_in_account_currency, gl.credit_in_account_currency,
            gl.debit, gl.credit,
        )
        .where(
            (gl.company == company)
            & (gl.posting_date <= as_of)
            & (gl.is_cancelled == 0)
            & (acc.account_type == account_type)
            & (gl.party.notnull())
            & (gl.party != "")
        )
    ).run(as_dict=True)

    by_party: dict = {}
    for r in rows:
        key = (r.party_type, r.party, r.account_currency or company_currency)
        acct_delta = ((r.debit_in_account_currency or 0.0) - (r.credit_in_account_currency or 0.0)) * sign
        base_delta = ((r.debit or 0.0) - (r.credit or 0.0)) * sign
        agg = by_party.get(key, (0.0, 0.0))
        by_party[key] = (agg[0] + acct_delta, agg[1] + base_delta)

    items = [
        {
            "party_type": pt,
            "party": p,
            "balance": _r(acct_bal),
            "currency": curr,
            "base_balance": _r(base_bal),
            "base_currency": company_currency,
        }
        for (pt, p, curr), (acct_bal, base_bal) in by_party.items()
        if abs(base_bal) > 0.005
    ]
    items.sort(key=lambda x: abs(x["base_balance"]), reverse=True)
    return items


def _account_qb_filter(acc_qb, filters: dict):
    pred = None
    for k, v in filters.items():
        if isinstance(v, list) and len(v) == 2 and v[0] == "in":
            p = getattr(acc_qb, k).isin(v[1])
        else:
            p = getattr(acc_qb, k) == v
        pred = p if pred is None else (pred & p)
    return pred


def _recent_runs(company: str) -> list[dict]:
    return frappe.get_all(
        "Cashew Import Run",
        filters={"company": company},
        fields=[
            "name", "status", "company",
            "period_start", "period_end",
            "rows_total", "rows_valid", "rows_failed", "rows_posted", "rows_skipped",
            "modified",
        ],
        order_by="modified desc",
        limit=5,
        ignore_permissions=False,
    )
