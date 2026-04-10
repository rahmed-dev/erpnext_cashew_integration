"""
C007 — Async Worker + Progress Polling

``process_run`` is the function enqueued via ``frappe.enqueue``.
``process_revert`` cancels all posted ERP documents for a completed run.

Import flow:
  Draft → Queued  (set before enqueue by the API)
  Queued → Processing → Completed | Failed

Revert flow:
  Completed | Failed | Cancelled | Revert-Failed → Reverting (set by API)
  Reverting → Reverted | Revert-Failed

Progress is flushed to the run document every N rows (default 20, or site
config key ``cashew_progress_interval``).

Transfer pair coordination: the worker processes rows in order.  When it
encounters a Transfer row it checks whether the partner has already been
processed; if so it posts the pair immediately, otherwise it parks the first
leg and posts when the second arrives.
"""

import frappe
from frappe.utils import now

from cashew_integration.importer.idempotency import apply_idempotency_guard
from cashew_integration.importer.posting import post_row, post_transfer_pair
from cashew_integration.importer.validation import validate_rows_at_queue_time, validate_run_config
from cashew_integration.importer.diagnostics import generate_diagnostics_csv


# ── public: enqueue helper (called from API) ───────────────────────────────────

def enqueue_run(run_name: str) -> str:
    """Enqueue the import worker and return the job ID."""
    job = frappe.enqueue(
        "cashew_integration.importer.worker.process_run",
        run_name=run_name,
        queue="long",
        timeout=3600,
        enqueue_after_commit=True,
    )
    return getattr(job, "id", "")


# ── worker entry point ─────────────────────────────────────────────────────────

def process_run(run_name: str) -> None:
    """
    Main worker.  Called by the RQ worker process.

    All unhandled exceptions are caught, run status set to Failed, and the
    exception logged so it doesn't silently disappear.
    """
    try:
        _process(run_name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Cashew Import Failed: {run_name}")
        run = frappe.get_doc("Cashew Import Run", run_name)
        run.db_set("status",      "Failed",  notify=True)
        run.db_set("finished_on", now(),     notify=True)
        frappe.db.commit()
        raise


def _process(run_name: str) -> None:
    run = frappe.get_doc("Cashew Import Run", run_name)

    if run.status == "Cancelled":
        # Cancelled before worker started; exit quietly.
        return

    if run.status not in ("Queued",):
        frappe.throw(f"Run {run_name} is not in Queued status (current: {run.status}).")

    run.db_set("status",     "Processing", notify=True)
    run.db_set("started_on", now(),        notify=True)
    frappe.db.commit()

    # Reload rows from child table
    rows = [_row_to_dict(r) for r in run.import_rows]

    # Queue-time validation (may raise RUN_CONFIG_MISSING)
    validate_run_config(run, rows)
    validate_rows_at_queue_time(rows)

    # Idempotency guard
    apply_idempotency_guard(rows, run)

    progress_interval = int(
        frappe.conf.get("cashew_progress_interval", 20)
    )

    # Counters
    posted = failed = skipped = 0

    # Transfer pair state: row_idx -> row dict of the first-seen leg
    pending_transfer: dict[int, dict] = {}

    for i, row in enumerate(rows):
        if _is_run_cancelled(run_name):
            _update_counters(run, posted, failed, skipped)
            run.db_set("finished_on", now(), notify=True)
            frappe.db.commit()
            return

        status = row.get("validation_status")

        if status == "Skipped":
            skipped += 1
            _write_row_result(run, row)
            continue

        if status == "Error":
            failed += 1
            _write_row_result(run, row)
            continue

        # Transfer JV: needs both legs
        if row.get("txn_type") == "Transfer":
            partner_idx = row.get("transfer_pair_row_idx")
            if partner_idx and partner_idx in pending_transfer:
                source_row = pending_transfer.pop(partner_idx)
                dest_row   = row
                # canonical: source = income_flag false, dest = income_flag true
                if source_row.get("income_flag") == "true":
                    source_row, dest_row = dest_row, source_row
                try:
                    doctype, docname = post_transfer_pair(source_row, dest_row, run)
                    if doctype:
                        for leg in (source_row, dest_row):
                            leg["posted_doctype"]  = doctype
                            leg["posted_docname"]  = docname
                            leg["posted_gl_date"]  = source_row["txn_date"]
                            leg["validation_status"] = "Valid"
                        _write_row_result(run, source_row)
                        _write_row_result(run, dest_row)
                        posted += 2
                    else:
                        # imbalance error — both legs already marked Error by posting engine
                        for leg in (source_row, dest_row):
                            _write_row_result(run, leg)
                        failed += 2
                except Exception as exc:
                    _mark_row_error(source_row, str(exc))
                    _mark_row_error(dest_row,   str(exc))
                    _write_row_result(run, source_row)
                    _write_row_result(run, dest_row)
                    failed += 2
                    frappe.log_error(frappe.get_traceback(),
                                     f"Cashew Transfer Pair Error: run={run.name}")
            else:
                # First leg seen: park it
                pending_transfer[row["row_idx"]] = row
                continue
        else:
            try:
                doctype, docname = post_row(row, run)
                row["posted_doctype"]    = doctype
                row["posted_docname"]    = docname
                row["posted_gl_date"]    = row["txn_date"]
                row["validation_status"] = "Valid"
                _write_row_result(run, row)
                posted += 1
            except Exception as exc:
                _mark_row_error(row, str(exc))
                _write_row_result(run, row)
                failed += 1
                frappe.log_error(frappe.get_traceback(),
                                 f"Cashew Row Error: run={run.name} row={row['row_idx']}")

        # Flush progress periodically
        if (i + 1) % progress_interval == 0:
            _update_counters(run, posted, failed, skipped)
            frappe.db.commit()

    # Any remaining unmatched Transfer legs: mark as errors
    for row in pending_transfer.values():
        _mark_row_error(row, "Transfer pair partner was never encountered in the file.")
        row["validation_error_code"] = "TRANSFER_PAIR_INCOMPLETE"
        _write_row_result(run, row)
        failed += 1

    _update_counters(run, posted, failed, skipped)

    # Diagnostics CSV (C008)
    try:
        diag_file = generate_diagnostics_csv(rows, run)
        run.db_set("diagnostics_file", diag_file, notify=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(),
                         f"Cashew Diagnostics CSV Error: run={run.name}")

    final_status = "Failed" if failed > 0 else "Completed"
    run.db_set("status",      final_status, notify=True)
    run.db_set("finished_on", now(),        notify=True)
    frappe.db.commit()


# ── revert: enqueue helper ────────────────────────────────────────────────────

def enqueue_revert(run_name: str) -> str:
    """Enqueue the revert worker and return the job ID."""
    job = frappe.enqueue(
        "cashew_integration.importer.worker.process_revert",
        run_name=run_name,
        queue="long",
        timeout=3600,
        enqueue_after_commit=True,
    )
    return getattr(job, "id", "")


# ── revert: worker entry point ────────────────────────────────────────────────

def process_revert(run_name: str) -> None:
    """
    Revert worker.  Called by the RQ worker process.
    Cancels every posted SI/PI/JE recorded on the run's rows.
    """
    try:
        _revert(run_name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Cashew Revert Failed: {run_name}")
        run = frappe.get_doc("Cashew Import Run", run_name)
        run.db_set("status",      "Revert-Failed", notify=True)
        run.db_set("finished_on", now(),            notify=True)
        frappe.db.commit()
        raise


def _revert(run_name: str) -> None:
    run = frappe.get_doc("Cashew Import Run", run_name)

    if run.status != "Reverting":
        frappe.throw(f"Run {run_name} is not in Reverting status (current: {run.status}).")

    progress_interval = int(frappe.conf.get("cashew_progress_interval", 20))

    # Load only rows that have a posted document and haven't been successfully reverted yet.
    rows = frappe.get_all(
        "Cashew Import Row",
        filters={"parent": run_name, "posted_docname": ["!=", ""]},
        fields=["name", "row_idx", "posted_doctype", "posted_docname", "revert_status"],
        order_by="row_idx asc",
    )

    reverted = failed = 0

    for i, row in enumerate(rows):
        # Idempotent: already-reverted rows from a previous partial run are skipped.
        if row.get("revert_status") == "Reverted":
            reverted += 1
            continue

        doctype = row.get("posted_doctype")
        docname = row.get("posted_docname")

        if not doctype or not docname:
            continue

        try:
            doc = frappe.get_doc(doctype, docname)

            if doc.docstatus == 2:
                # Already cancelled externally — treat as success.
                frappe.db.set_value("Cashew Import Row", row["name"], {
                    "revert_status": "Reverted",
                    "revert_error":  None,
                    "posted_doctype": None,
                    "posted_docname": None,
                })
                reverted += 1

            elif doc.docstatus == 1:
                doc.cancel()
                frappe.db.set_value("Cashew Import Row", row["name"], {
                    "revert_status": "Reverted",
                    "revert_error":  None,
                    "posted_doctype": None,
                    "posted_docname": None,
                })
                reverted += 1

            else:
                frappe.db.set_value("Cashew Import Row", row["name"], {
                    "revert_status": "Revert-Failed",
                    "revert_error":  f"{doctype} {docname} is in Draft status — cannot cancel.",
                })
                failed += 1

        except Exception as exc:
            frappe.log_error(
                frappe.get_traceback(),
                f"Cashew Revert Row Error: run={run_name} doc={docname}",
            )
            frappe.db.set_value("Cashew Import Row", row["name"], {
                "revert_status": "Revert-Failed",
                "revert_error":  str(exc)[:500],
            })
            failed += 1

        if (i + 1) % progress_interval == 0:
            frappe.db.commit()

    frappe.db.commit()

    final_status = "Revert-Failed" if failed > 0 else "Reverted"
    run.db_set("status",      final_status, notify=True)
    run.db_set("finished_on", now(),        notify=True)
    frappe.db.commit()


# ── helpers ────────────────────────────────────────────────────────────────────

def _row_to_dict(child_row) -> dict:
    """Convert a Cashew Import Row child doc to a plain dict the engine can mutate."""
    return {f: child_row.get(f) for f in child_row.meta.get_fieldnames_with_value()}


def _write_row_result(run, row: dict) -> None:
    """Persist result fields back to the child table row via db.set_value."""
    frappe.db.set_value(
        "Cashew Import Row",
        {"parent": run.name, "row_idx": row["row_idx"]},
        {
            "validation_status":       row.get("validation_status"),
            "validation_error_code":   row.get("validation_error_code"),
            "validation_error_message": row.get("validation_error_message"),
            "posted_doctype":          row.get("posted_doctype"),
            "posted_docname":          row.get("posted_docname"),
            "posted_gl_date":          row.get("posted_gl_date"),
            "is_duplicate":            row.get("is_duplicate", 0),
            "exchange_rate":           row.get("exchange_rate"),
            "base_amount":             row.get("base_amount"),
            "transfer_pair_row_idx":   row.get("transfer_pair_row_idx"),
            "resolved_party":          row.get("resolved_party"),
            "resolved_party_type":     row.get("resolved_party_type"),
            "party_source":            row.get("party_source"),
            "resolved_route":          row.get("resolved_route"),
            "resolved_account":        row.get("resolved_account"),
            "resolved_income_account": row.get("resolved_income_account"),
            "resolved_expense_account": row.get("resolved_expense_account"),
            "resolved_erp_account":    row.get("resolved_erp_account"),
            "resolved_external_account": row.get("resolved_external_account"),
        },
    )


def _update_counters(run, posted: int, failed: int, skipped: int) -> None:
    run.db_set("rows_posted",  posted,  notify=True)
    run.db_set("rows_failed",  failed,  notify=True)
    run.db_set("rows_skipped", skipped, notify=True)


def _mark_row_error(row: dict, message: str) -> None:
    row["validation_status"]        = "Error"
    row["validation_error_code"]    = row.get("validation_error_code") or "POSTING_ERROR"
    row["validation_error_message"] = message


def _is_run_cancelled(run_name: str) -> bool:
    status = frappe.db.get_value("Cashew Import Run", run_name, "status")
    return status == "Cancelled"
