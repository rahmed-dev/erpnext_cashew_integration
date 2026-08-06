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

import uuid

import frappe
from frappe.utils import now

from cashew_integration.importer.errors import set_row_validation_error
from cashew_integration.importer.idempotency import apply_idempotency_guard
from cashew_integration.importer.posting import post_row, post_transfer_pair
from cashew_integration.importer.resync import apply_supersessions, screen_resyncs
from cashew_integration.importer.realtime import emit_row_update, emit_run_progress
from cashew_integration.importer.validation import validate_rows_at_queue_time, validate_run_config
from cashew_integration.importer.diagnostics import generate_diagnostics_csv


_ROW_PATCH_FIELDS = (
    "validation_status", "validation_error_code", "validation_error_message",
    "posted_doctype", "posted_docname", "posted_gl_date",
    "is_duplicate", "exchange_rate", "base_amount",
    "transfer_pair_row_idx", "resolved_party", "resolved_party_type",
    "party_source", "resolved_route", "resolved_account",
    "resolved_external_account", "revert_status", "revert_error",
    "supersedes", "superseded_by",
)


# ── public: enqueue helper (called from API) ───────────────────────────────────

def enqueue_run(run_name: str) -> str:
    """Enqueue the import worker and return the job ID."""
    job_id = str(uuid.uuid4())
    frappe.enqueue(
        "cashew_integration.importer.worker.process_run",
        run_name=run_name,
        queue="long",
        timeout=3600,
        job_id=job_id,
        enqueue_after_commit=True,
    )
    return job_id


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
        emit_run_progress(run_name, {"status": "Failed", "finished_on": str(run.finished_on)})
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
    emit_run_progress(run_name, {"status": "Processing", "started_on": str(run.started_on)})

    # Reload rows from child table
    rows = [_row_to_dict(r) for r in run.import_rows]

    # Queue-time validation (may raise RUN_CONFIG_MISSING)
    validate_run_config(run, rows)
    validate_rows_at_queue_time(rows)

    # Idempotency guard (also tags rows whose source was edited upstream)
    apply_idempotency_guard(rows, run)

    # Resync pre-flight. Runs BEFORE the posting loop so a row that cannot legally
    # supersede its predecessor is refused while refusing is still free — once the
    # replacement is posted, declining to cancel the original means two live entries.
    screen_resyncs(rows, run)

    progress_interval = int(
        frappe.conf.get("cashew_progress_interval", 20)
    )

    # Counters. `resynced` is a subset of `posted`, not a fourth outcome — a resynced
    # row did post, it just replaced a stale document on the way. Reported separately
    # because "the import rewrote submitted GL" deserves to be visible.
    posted = failed = skipped = resynced = 0

    # Transfer pair state: row_idx -> row dict of the first-seen leg
    pending_transfer: dict[int, dict] = {}

    for i, row in enumerate(rows):
        if _is_run_cancelled(run_name):
            _update_counters(run, posted, failed, skipped, resynced)
            run.db_set("finished_on", now(), notify=True)
            frappe.db.commit()
            emit_run_progress(run_name, {"status": "Cancelled", "finished_on": str(run.finished_on)})
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
                # Deliberately unaware of resync: superseding is a property of the
                # run, applied uniformly after this loop, not a fourth posting route
                # only non-Transfer rows would reach.
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
            _update_counters(run, posted, failed, skipped, resynced)
            frappe.db.commit()

    # Any remaining unmatched Transfer legs: mark as errors
    for row in pending_transfer.values():
        set_row_validation_error(
            row, "TRANSFER_PAIR_INCOMPLETE",
            "Transfer pair partner was never encountered in the file.",
        )
        _write_row_result(run, row)
        failed += 1

    # Everything that was going to post has posted. Only now cancel the documents
    # those postings replaced — the replacement provably exists, so the period is
    # never left with neither entry.
    resynced, supersede_failed = apply_supersessions(rows, run)
    failed += supersede_failed

    if resynced or supersede_failed:
        # Rows are re-written because apply_supersessions stamps revert_status,
        # supersedes and superseded_by after the loop already persisted them.
        for row in rows:
            if row.get("revert_status"):
                _write_row_result(run, row)
        # An import that rewrites already-submitted GL must leave a trail somewhere
        # a person will actually look, not only on the individual rows.
        frappe.log_error(
            frappe.as_json([
                {
                    "row_idx":     r.get("row_idx"),
                    "source_pk":   r.get("source_pk"),
                    "superseded":  (r.get("_resync_of") or {}).get("posted_docname"),
                    "replaced_by": r.get("posted_docname"),
                    "amount":      r.get("raw_amount"),
                    "outcome":     r.get("revert_status"),
                }
                for r in rows if r.get("_resync_of")
            ], indent=2),
            f"Cashew Import Resynced Edited Rows: {run.name}",
        )

    _update_counters(run, posted, failed, skipped, resynced)

    # Budgets (f012 c012) — reference data, imported alongside the run but OUTSIDE
    # it. Deliberately after the counters are final: this step must never move
    # them, never change the run's status, and never fail the run.
    _import_budgets(run)

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
    emit_run_progress(run_name, {
        "status":       final_status,
        "rows_posted":  posted,
        "rows_failed":  failed,
        "rows_skipped": skipped,
        "rows_resynced": resynced,
        "finished_on":  str(run.finished_on),
    })


# ── budgets (f012 c012) ───────────────────────────────────────────────────────

def _import_budgets(run) -> None:
    """Upsert the backup's budgets. Swallows every failure by design.

    Budgets are reference data: they are worth having, and never worth failing a
    posted ledger import over. A budget with an unrecognised reoccurrence, an
    unmapped scope member, or an unreadable budgets table leaves the ledger
    exactly as it is and shows up in the Error Log instead.

    SQLite-only: the CSV export carries no budgets at all.
    """
    if run.source_type != "SQLite" or not run.source_file:
        return

    try:
        from cashew_integration.api import _read_attached_file
        from cashew_integration.importer.budgets import import_budgets
        from cashew_integration.importer.sqlite_reader import read_budgets

        budgets = read_budgets(_read_attached_file(run.source_file))
        if not budgets:
            return
        summary = import_budgets(budgets, run.company, run.name)
        frappe.db.commit()
    except Exception:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(),
                         f"Cashew Budget Import Error: run={run.name}")
        return

    if summary.get("skipped"):
        # A skipped budget is a mapping gap, not a bug — recorded where a person
        # will look, and fixed by mapping the member and re-running the import.
        frappe.log_error(
            frappe.as_json(summary["skipped"], indent=2),
            f"Cashew Budgets Not Imported (unmapped scope): {run.name}",
        )


# ── revert: enqueue helper ────────────────────────────────────────────────────

def enqueue_revert(run_name: str) -> str:
    """Enqueue the revert worker and return the job ID."""
    job_id = str(uuid.uuid4())
    frappe.enqueue(
        "cashew_integration.importer.worker.process_revert",
        run_name=run_name,
        queue="long",
        timeout=3600,
        job_id=job_id,
        enqueue_after_commit=True,
    )
    return job_id


# ── revert: worker entry point ────────────────────────────────────────────────

def process_revert(run_name: str) -> None:
    """
    Revert worker.  Called by the RQ worker process.
    Cancels every posted SI/PI/JE recorded on the run's rows.
    """
    # Marks our own cancels so the Journal Entry doc_events (c-reconcile) don't
    # misreport them as external cancellations.
    frappe.flags.cashew_reverting = run_name
    try:
        _revert(run_name)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Cashew Revert Failed: {run_name}")
        run = frappe.get_doc("Cashew Import Run", run_name)
        run.db_set("status",      "Revert-Failed", notify=True)
        run.db_set("finished_on", now(),            notify=True)
        frappe.db.commit()
        emit_run_progress(run_name, {"status": "Revert-Failed", "finished_on": str(run.finished_on)})
        raise
    finally:
        frappe.flags.cashew_reverting = None


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
                patch = {
                    "revert_status": "Reverted",
                    "revert_error":  None,
                    "posted_doctype": None,
                    "posted_docname": None,
                }
                frappe.db.set_value("Cashew Import Row", row["name"], patch)
                emit_row_update(run_name, {"row_idx": row["row_idx"], **patch})
                reverted += 1

            elif doc.docstatus == 1:
                doc.cancel()
                patch = {
                    "revert_status": "Reverted",
                    "revert_error":  None,
                    "posted_doctype": None,
                    "posted_docname": None,
                }
                frappe.db.set_value("Cashew Import Row", row["name"], patch)
                emit_row_update(run_name, {"row_idx": row["row_idx"], **patch})
                reverted += 1

            else:
                patch = {
                    "revert_status": "Revert-Failed",
                    "revert_error":  f"{doctype} {docname} is in Draft status — cannot cancel.",
                }
                frappe.db.set_value("Cashew Import Row", row["name"], patch)
                emit_row_update(run_name, {"row_idx": row["row_idx"], **patch})
                failed += 1

        except Exception as exc:
            frappe.log_error(
                frappe.get_traceback(),
                f"Cashew Revert Row Error: run={run_name} doc={docname}",
            )
            patch = {
                "revert_status": "Revert-Failed",
                "revert_error":  str(exc)[:500],
            }
            frappe.db.set_value("Cashew Import Row", row["name"], patch)
            emit_row_update(run_name, {"row_idx": row["row_idx"], **patch})
            failed += 1

        if (i + 1) % progress_interval == 0:
            frappe.db.commit()

    frappe.db.commit()

    final_status = "Revert-Failed" if failed > 0 else "Reverted"
    run.db_set("status",      final_status, notify=True)
    run.db_set("finished_on", now(),        notify=True)
    frappe.db.commit()
    emit_run_progress(run_name, {"status": final_status, "finished_on": str(run.finished_on)})


# ── helpers ────────────────────────────────────────────────────────────────────

def _row_to_dict(child_row) -> dict:
    """Convert a Cashew Import Row child doc to a plain dict the engine can mutate."""
    return {f: child_row.get(f) for f in child_row.meta.get_fieldnames_with_value()}


def _write_row_result(run, row: dict) -> None:
    """Persist result fields back to the child table row via db.set_value.

    Emits a synthetic parent-run `doc_update` carrying the row patch
    so the SPA (c008) can apply per-row updates without polling.
    """
    patch = {
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
    }

    # The revert lifecycle belongs to reconcile.py and process_revert — the posting
    # path may only add to it. Writing these unconditionally blanks a stamp it does
    # not own: re-queue a Failed run and every "Cancelled Externally" mark reconcile
    # made would be erased. `if key in row` is not a usable test here — _row_to_dict
    # builds from get_fieldnames_with_value(), so every field is present as None.
    for field in ("revert_status", "revert_error", "supersedes", "superseded_by"):
        if row.get(field):
            patch[field] = row[field]

    frappe.db.set_value(
        "Cashew Import Row",
        {"parent": run.name, "row_idx": row["row_idx"]},
        patch,
    )
    emit_row_update(run.name, _row_patch(row))


def _row_patch(row: dict) -> dict:
    """Build a compact realtime patch dict from a row's current state."""
    patch = {"row_idx": row.get("row_idx")}
    for field in _ROW_PATCH_FIELDS:
        if field in row:
            patch[field] = row.get(field)
    return patch


def _update_counters(run, posted: int, failed: int, skipped: int, resynced: int = 0) -> None:
    run.db_set("rows_posted",   posted,   notify=True)
    run.db_set("rows_failed",   failed,   notify=True)
    run.db_set("rows_skipped",  skipped,  notify=True)
    run.db_set("rows_resynced", resynced, notify=True)
    emit_run_progress(run.name, {
        "rows_posted":   posted,
        "rows_failed":   failed,
        "rows_skipped":  skipped,
        "rows_resynced": resynced,
    })


def _mark_row_error(row: dict, message: str) -> None:
    code = row.get("validation_error_code") or "POSTING_ERROR"
    set_row_validation_error(row, code, message)


def _is_run_cancelled(run_name: str) -> bool:
    status = frappe.db.get_value("Cashew Import Run", run_name, "status")
    return status == "Cancelled"
