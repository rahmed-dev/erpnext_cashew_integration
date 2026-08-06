"""
Stamp Import Rows whose posted document was cancelled or deleted outside the
app's revert flow.

Before the Journal Entry ``doc_events`` existed, a Desk cancel left the row
still reporting itself as posted with an empty ``revert_status``, so the run
looked clean while its GL impact was gone. This backfills the rows that were
already in that state.

Data only — no GL is written. Whether to re-post the affected transaction is a
judgement call for the accountant, and the stamped row is what makes that call
visible.
"""

import frappe

from cashew_integration.importer.reconcile import EXTERNAL_CANCELLED, EXTERNAL_DELETED


def execute():
    rows = frappe.get_all(
        "Cashew Import Row",
        filters={"posted_docname": ["is", "set"], "revert_status": ["in", ["", None]]},
        fields=["name", "parent", "row_idx", "posted_doctype", "posted_docname"],
    )

    cancelled = deleted = 0

    for row in rows:
        doctype = row.posted_doctype or "Journal Entry"
        docstatus = frappe.db.get_value(doctype, row.posted_docname, "docstatus")

        if docstatus is None:
            frappe.db.set_value("Cashew Import Row", row.name, {
                "revert_status": EXTERNAL_DELETED,
                "revert_error": (
                    f"{doctype} {row.posted_docname} does not exist. Detected by "
                    "backfill; the document was deleted outside the revert flow."
                ),
            }, update_modified=False)
            deleted += 1

        elif docstatus == 2:
            frappe.db.set_value("Cashew Import Row", row.name, {
                "revert_status": EXTERNAL_CANCELLED,
                "revert_error": (
                    f"{doctype} {row.posted_docname} is cancelled and contributes no "
                    "GL. Detected by backfill; it was cancelled outside the revert "
                    "flow, so this row's amount is missing from the ledger."
                ),
            }, update_modified=False)
            cancelled += 1

    if cancelled or deleted:
        print(
            f"cashew: flagged {cancelled} externally-cancelled and {deleted} "
            f"deleted posted documents"
        )
