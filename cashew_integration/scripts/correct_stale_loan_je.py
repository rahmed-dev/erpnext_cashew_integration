"""
Correct the one loan Journal Entry that holds a pre-edit amount.

On 2026-06-29 a loan to Customer HC was recorded in Cashew at 150,000.00 and imported.
On 2026-07-07 05:55:38 UTC it was edited down to 148,674.00, and seventeen seconds
later the 1,326.00 difference was entered as its own transaction. Cashew holds both
halves; ERPNext imported the new 1,326.00 line but never revisited the edited loan, so
the ledger still carries 150,000.00 and counts the 1,326.00 twice. That is the whole of
the Petty Cash gap, bar 2.00 explained by the PC Build being a 13,748.00 Purchase
Invoice against Cashew's 13,750.00 note.

``importer/resync.py`` stops this recurring, but only for rows imported from a SQLite
backup — they are the only ones that carry a ``source_pk``. This entry predates that
and is corrected by hand.

The Journal Entry is deliberately NOT identified by name: it is ``ACC-JV-2026-00565``
on erp.nstack.xyz and ``ACC-JV-2026-00375`` on work.local. It is found by content, and
the script refuses to write unless exactly one row matches.

Writes GL, so it never runs from a migration. Dry run first::

    bench --site <site> execute \\
      cashew_integration.scripts.correct_stale_loan_je.run

Then apply::

    bench --site <site> execute \\
      cashew_integration.scripts.correct_stale_loan_je.run \\
      --kwargs "{'apply': True}"
"""

import frappe
from frappe.utils import flt

from cashew_integration.importer.posting import post_row
from cashew_integration.importer.resync import RESYNCED
from cashew_integration.importer.worker import _row_to_dict

# The transaction, as Cashew records it before and after the edit.
_TXN_DATE = "2026-06-29"
_STALE_AMOUNT = 150000.00
_CORRECT_AMOUNT = 148674.00
_ACCOUNT_HINT = "Petty Cash"
_ROUTE = "Loan Receivable JE"


def run(apply: bool = False, company: str | None = None):
    """Find and optionally correct the stale loan entry."""
    matches = _find(company)

    if not matches:
        print(f"cashew: no submitted {_ROUTE} of {_STALE_AMOUNT:,.2f} on {_TXN_DATE} "
              f"against {_ACCOUNT_HINT}. Nothing to correct — already fixed, or this "
              "site does not carry that import.")
        return []

    for m in matches:
        print(f"  {m['journal_entry']}  {m['txn_date']}  {m['account']}  "
              f"{m['raw_amount']:,.2f} -> {_CORRECT_AMOUNT:,.2f}  "
              f"(row {m['row_idx']} of {m['run']}, party {m['party'] or '-'})")

    if len(matches) > 1:
        print(f"cashew: REFUSING — expected exactly 1 match, found {len(matches)}. "
              "Correcting the wrong entry is worse than leaving this one stale. "
              "Narrow with company=, or correct by hand.")
        return matches

    if not apply:
        print("cashew: 1 entry would be corrected. Re-run with "
              "--kwargs \"{'apply': True}\" to write.")
        return matches

    _correct(matches[0])
    frappe.db.commit()
    return matches


def _find(company: str | None) -> list[dict]:
    rows = frappe.get_all(
        "Cashew Import Row",
        filters={
            "txn_type": "Loan Receivable",
            "txn_date": _TXN_DATE,
            "posted_docname": ["is", "set"],
        },
        fields=["name", "parent", "row_idx", "raw_amount", "posted_doctype",
                "posted_docname", "resolved_erp_account", "resolved_party",
                "resolved_route"],
    )

    out = []
    for row in rows:
        if abs(flt(row.raw_amount) - _STALE_AMOUNT) > 0.005:
            continue
        if _ACCOUNT_HINT.lower() not in (row.resolved_erp_account or "").lower():
            continue

        run_company = frappe.db.get_value("Cashew Import Run", row.parent, "company")
        if company and run_company != company:
            continue

        docstatus = frappe.db.get_value(
            row.posted_doctype or "Journal Entry", row.posted_docname, "docstatus"
        )
        if docstatus != 1:
            continue  # already cancelled or replaced

        out.append({
            "row_name":      row.name,
            "run":           row.parent,
            "company":       run_company,
            "row_idx":       row.row_idx,
            "raw_amount":    flt(row.raw_amount),
            "txn_date":      _TXN_DATE,
            "account":       row.resolved_erp_account,
            "party":         row.resolved_party,
            "doctype":       row.posted_doctype or "Journal Entry",
            "journal_entry": row.posted_docname,
        })

    return out


def _correct(case: dict) -> None:
    run_doc = frappe.get_doc("Cashew Import Run", case["run"])
    child = next((r for r in run_doc.import_rows if r.row_idx == case["row_idx"]), None)
    if child is None:
        print(f"  SKIP {case['journal_entry']}: row {case['row_idx']} not found on "
              f"{case['run']}")
        return

    row = _row_to_dict(child)
    row["raw_amount"] = _CORRECT_AMOUNT
    # PKR against a PKR company, so the rate stays 1.0 and base tracks raw.
    if flt(row.get("exchange_rate")) in (0.0, 1.0):
        row["exchange_rate"] = 1.0
        row["base_amount"] = _CORRECT_AMOUNT
    else:
        row["base_amount"] = round(_CORRECT_AMOUNT * flt(row["exchange_rate"]), 2)

    # Post the replacement BEFORE cancelling. The reverse order risks leaving the
    # period with neither entry if the repost fails.
    doctype, docname = post_row(row, run_doc)
    if not doctype:
        print(f"  FAILED {case['journal_entry']}: "
              f"{row.get('validation_error_message')}. Original left submitted.")
        return

    # Our own cancel — keeps reconcile.on_document_cancelled from calling it external.
    frappe.flags.cashew_reverting = case["run"]
    try:
        frappe.get_doc(case["doctype"], case["journal_entry"]).cancel()
    finally:
        frappe.flags.cashew_reverting = None

    frappe.db.set_value("Cashew Import Row", case["row_name"], {
        "raw_amount":     _CORRECT_AMOUNT,
        "base_amount":    row["base_amount"],
        "exchange_rate":  row["exchange_rate"],
        "posted_doctype": doctype,
        "posted_docname": docname,
        "revert_status":  RESYNCED,
        "revert_error": (
            f"Source transaction was edited in Cashew on 2026-07-07 from "
            f"{_STALE_AMOUNT:,.2f} to {_CORRECT_AMOUNT:,.2f}. "
            f"{case['doctype']} {case['journal_entry']} cancelled and replaced by "
            f"{doctype} {docname}."
        )[:500],
    }, update_modified=False)

    print(f"  {case['journal_entry']} cancelled, reposted as {docname} at "
          f"{_CORRECT_AMOUNT:,.2f}")
