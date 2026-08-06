"""
Recompute Import Run counters from the child table.

Desk's Duplicate copies field values verbatim, and none of the lifecycle fields
were ``no_copy``. A duplicated run inherited another run's status, counters and
start/finish timestamps, producing records that claimed to have posted dozens of
rows while owning no documents at all — one had a ``started_on`` earlier than its
own ``creation``.

``no_copy`` plus the controller's new-run guard stop it happening again. This
repairs the records already written.

``rows_posted`` is a lifetime counter — revert clears ``posted_docname`` but the
fact that rows were once posted stays meaningful — so it is only rewritten when
the run owns no documents whatsoever, which is the unambiguous phantom case.
"""

import frappe


def execute():
    runs = frappe.get_all(
        "Cashew Import Run",
        fields=["name", "status", "rows_total", "rows_valid", "rows_failed",
                "rows_skipped", "rows_posted", "started_on", "finished_on"],
    )

    repaired = 0

    for run in runs:
        rows = frappe.get_all(
            "Cashew Import Row",
            filters={"parent": run.name, "parenttype": "Cashew Import Run"},
            fields=["validation_status", "posted_docname"],
        )

        patch = {
            "rows_total": len(rows),
            "rows_valid": sum(1 for r in rows if r.validation_status == "Valid"),
            "rows_failed": sum(1 for r in rows if r.validation_status == "Error"),
            "rows_skipped": sum(1 for r in rows if r.validation_status == "Skipped"),
        }

        owns_documents = frappe.db.exists(
            "Journal Entry", {"cashew_import_run": run.name}
        )
        if not rows and not owns_documents:
            # Never parsed, never posted, owns nothing — a phantom run.
            patch["rows_posted"] = 0
            patch["started_on"] = None
            patch["finished_on"] = None

        changed = {k: v for k, v in patch.items() if run.get(k) != v}
        if not changed:
            continue

        frappe.db.set_value("Cashew Import Run", run.name, changed,
                            update_modified=False)
        repaired += 1
        print(f"cashew: resynced counters on {run.name}: {changed}")

    if repaired:
        print(f"cashew: repaired {repaired} import run(s)")
