"""
Drift detection between Cashew Import Rows and the ERP documents they claim.

The importer was write-once: it stamped ``posted_docname`` on a row and never
looked at that document again. Anything done to the document afterwards outside
the app's own revert path — a Desk cancel, a delete, an amend — left the row
still reporting itself as posted, so the run's own statistics called it clean
while the GL said otherwise.

Two mechanisms close that gap:

1. **Live** — ``doc_events`` on Journal Entry fire ``on_document_cancelled`` /
   ``on_document_trashed``, which stamp the owning row the moment it happens.
2. **Sweep** — ``reconcile_run`` re-reads every claimed document and reports
   drift. Safe to call at any time; it never writes GL.

``frappe.flags.cashew_reverting`` marks the app's own revert worker so its
cancels are not misreported as external.
"""

import frappe


# Values written to Cashew Import Row.revert_status by the live hooks.
EXTERNAL_CANCELLED = "Cancelled Externally"
EXTERNAL_DELETED = "Deleted Externally"

# Written by importer/resync.py. Imported by name rather than from that module to
# keep the dependency one-way: resync already reaches into this module's flag.
SUPERSEDED = "Superseded"
RESYNCED = "Resynced"


# ── live hooks ─────────────────────────────────────────────────────────────────

def on_document_cancelled(doc, method=None) -> None:
    """Stamp owning rows when a Cashew-posted document is cancelled outside revert."""
    if frappe.flags.get("cashew_reverting"):
        return
    _stamp_rows(
        doc,
        EXTERNAL_CANCELLED,
        f"{doc.doctype} {doc.name} was cancelled outside the import's revert flow. "
        "Its GL impact is gone but this row still claims it as posted.",
    )


def on_document_trashed(doc, method=None) -> None:
    """Stamp owning rows when a Cashew-posted document is deleted."""
    if frappe.flags.get("cashew_reverting"):
        return
    _stamp_rows(
        doc,
        EXTERNAL_DELETED,
        f"{doc.doctype} {doc.name} was deleted. This row's posted document no "
        "longer exists.",
    )


def _stamp_rows(doc, status: str, message: str) -> None:
    if not doc.get("cashew_import_run"):
        return

    rows = frappe.get_all(
        "Cashew Import Row",
        filters={"posted_docname": doc.name, "posted_doctype": doc.doctype},
        fields=["name", "parent", "row_idx", "revert_status"],
    )
    for row in rows:
        # A Superseded row's document was cancelled by an import that replaced it.
        # Deleting that cancelled document later must not overwrite the lineage with
        # "Deleted Externally" — the successor is what carries the GL, and losing the
        # pointer to it would turn a recorded replacement back into unexplained drift.
        if row.revert_status in ("Reverted", SUPERSEDED, status):
            continue
        frappe.db.set_value(
            "Cashew Import Row",
            row.name,
            {"revert_status": status, "revert_error": message[:500]},
            update_modified=False,
        )


# ── sweep ──────────────────────────────────────────────────────────────────────

def reconcile_run(run_name: str) -> dict:
    """
    Re-read every document claimed by *run_name* and report drift.

    Read-only. Returns::

        {
          "run": ..., "status": ..., "checked": n,
          "clean": bool,
          "counters": {"stored": {...}, "actual": {...}, "drift": bool},
          "issues": [{"row_idx", "doctype", "docname", "problem", "detail"}, ...],
          "orphans": [docname, ...],
        }

    ``orphans`` are documents stamped with this run that no row claims — the
    mirror image of the row-side checks, and the only way to catch a document
    the importer created but failed to record.
    """
    run = frappe.get_doc("Cashew Import Run", run_name)

    rows = frappe.get_all(
        "Cashew Import Row",
        filters={"parent": run_name, "parenttype": "Cashew Import Run"},
        fields=[
            "name", "row_idx", "txn_date", "raw_amount", "base_amount",
            "posted_doctype", "posted_docname", "validation_status",
            "revert_status", "superseded_by", "txn_type",
        ],
        order_by="row_idx asc",
    )

    issues: list[dict] = []
    checked = 0

    for row in rows:
        docname = row.posted_docname
        if not docname:
            continue
        doctype = row.posted_doctype or "Journal Entry"
        checked += 1

        if not frappe.db.exists(doctype, docname):
            issues.append(_issue(row, doctype, docname, "missing",
                                 "Document no longer exists."))
            continue

        docstatus, posting_date = frappe.db.get_value(
            doctype, docname, ["docstatus", "posting_date"]
        )

        if docstatus == 2:
            # A supersession is a recorded replacement, not drift: the GL impact
            # moved to a named successor rather than disappearing. That claim is
            # VERIFIED here rather than taken on the strength of a status string —
            # a cancelled document whose replacement is also gone is real drift, and
            # only storing the successor's name makes the two distinguishable.
            if row.revert_status == SUPERSEDED:
                successor = row.superseded_by
                if (
                    successor
                    and frappe.db.exists(doctype, successor)
                    and frappe.db.get_value(doctype, successor, "docstatus") == 1
                ):
                    continue
                issues.append(_issue(
                    row, doctype, docname, "supersession-broken",
                    f"Row was superseded by {successor or '(unrecorded)'}, but that "
                    "document is missing or not submitted — the GL impact of this "
                    "transaction is now absent entirely.",
                ))
                continue
            issues.append(_issue(row, doctype, docname, "cancelled",
                                 "Document is cancelled but the row still claims it."))
            continue
        if docstatus == 0:
            issues.append(_issue(row, doctype, docname, "draft",
                                 "Document was never submitted, so it has no GL impact."))
            continue

        if row.txn_date and str(posting_date) != str(row.txn_date):
            issues.append(_issue(row, doctype, docname, "date-drift",
                                 f"Row date {row.txn_date} vs document {posting_date}."))

    orphans = _find_orphans(run_name, {r.posted_docname for r in rows if r.posted_docname})
    counters = _counter_drift(run, rows)

    return {
        "run": run_name,
        "status": run.status,
        "checked": checked,
        "clean": not issues and not orphans and not counters["drift"],
        "counters": counters,
        "issues": issues,
        "orphans": orphans,
    }


def _issue(row, doctype, docname, problem, detail) -> dict:
    return {
        "row_idx": row.row_idx,
        "doctype": doctype,
        "docname": docname,
        "problem": problem,
        "detail": detail,
    }


def _find_orphans(run_name: str, claimed: set) -> list[str]:
    """Submitted documents stamped with this run that no row claims."""
    stamped = frappe.get_all(
        "Journal Entry",
        filters={"cashew_import_run": run_name, "docstatus": 1},
        pluck="name",
    )
    return sorted(n for n in stamped if n not in claimed)


def _counter_drift(run, rows) -> dict:
    """Compare the run's stored counters against what its child rows actually say."""
    actual = {
        "rows_total": len(rows),
        "rows_valid": sum(1 for r in rows if r.validation_status == "Valid"),
        "rows_failed": sum(1 for r in rows if r.validation_status == "Error"),
        "rows_skipped": sum(1 for r in rows if r.validation_status == "Skipped"),
        "rows_posted": sum(1 for r in rows if r.posted_docname),
        "rows_resynced": sum(1 for r in rows if r.revert_status == RESYNCED),
    }
    stored = {k: int(run.get(k) or 0) for k in actual}

    # rows_posted is a lifetime counter: revert clears posted_docname but the
    # count of what was once posted stays meaningful, so a reverted run is
    # expected to disagree on it. That exemption does not extend to a run with no
    # child rows at all — a run claiming posted rows while owning nothing is the
    # phantom-duplicate signature, not a reverted run.
    compare = dict(actual)
    stored_cmp = dict(stored)
    reverted = run.status in ("Reverted", "Reverting", "Revert-Failed")
    if reverted and rows:
        compare.pop("rows_posted")
        stored_cmp.pop("rows_posted")
        # Revert overwrites revert_status with "Reverted", erasing the Resynced marks
        # the counter was built from. Same lifetime-counter argument as rows_posted.
        compare.pop("rows_resynced")
        stored_cmp.pop("rows_resynced")

    return {
        "stored": stored,
        "actual": actual,
        "drift": any(stored_cmp[k] != compare[k] for k in compare),
    }


def reconcile_all_runs() -> list[dict]:
    """Sweep every run that could still own GL. Logs anything unclean.

    Wired to the daily scheduler — the point is that drift surfaces on its own
    rather than waiting for someone to go looking.
    """
    names = frappe.get_all(
        "Cashew Import Run",
        filters={"status": ["in", ["Completed", "Failed", "Revert-Failed"]]},
        pluck="name",
    )
    unclean = []
    for name in names:
        try:
            report = reconcile_run(name)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Cashew Reconcile Error: {name}")
            continue
        if not report["clean"]:
            unclean.append(report)

    if unclean:
        frappe.log_error(
            frappe.as_json(unclean, indent=2),
            "Cashew Import Drift Detected",
        )
    return unclean
