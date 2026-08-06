"""
Backfill ``exchange_rate`` and ``base_amount`` on posted Transfer rows.

``apply_exchange_rates`` skips Transfer rows because the rate is only implied
once both legs are known, and the posting engine used to compute it without
writing it back. The GL was right, but every transfer row reported
``exchange_rate = 0`` and ``base_amount = 0``, so anything reading the child
table — diagnostics, the dashboard, any later reconciliation — undercounted
transfers by their full value.

The posting engine now stamps both fields at post time. This recovers the
figures for rows already posted by reading them back out of the GL entry the
row's own Journal Entry wrote.
"""

import frappe
from frappe.utils import flt


def execute():
    rows = frappe.get_all(
        "Cashew Import Row",
        filters={
            "txn_type": "Transfer",
            "posted_docname": ["is", "set"],
        },
        fields=["name", "parent", "row_idx", "raw_amount", "income_flag",
                "exchange_rate", "base_amount", "posted_doctype",
                "posted_docname", "resolved_erp_account"],
    )

    filled = skipped = 0

    for row in rows:
        if flt(row.exchange_rate) and flt(row.base_amount):
            continue
        if not row.resolved_erp_account:
            skipped += 1
            continue

        entry = _gl_leg(row)
        if not entry:
            skipped += 1
            continue

        base = abs(flt(entry.debit) - flt(entry.credit))
        account_amount = abs(
            flt(entry.debit_in_account_currency) - flt(entry.credit_in_account_currency)
        )
        if not account_amount:
            skipped += 1
            continue

        frappe.db.set_value("Cashew Import Row", row.name, {
            "exchange_rate": round(base / account_amount, 10),
            "base_amount": round(base, 2),
        }, update_modified=False)
        filled += 1

    print(f"cashew: backfilled rates on {filled} transfer row(s), skipped {skipped}")


def _gl_leg(row):
    """The GL entry this row's leg wrote: matched on account, then on direction.

    A transfer JE has one debit leg and one credit leg. When both legs happen to
    hit the same account the account filter alone is ambiguous, so ``income_flag``
    picks the side — income means money arrived, which is the debit.
    """
    entries = frappe.get_all(
        "GL Entry",
        filters={
            "voucher_no": row.posted_docname,
            "account": row.resolved_erp_account,
            "is_cancelled": 0,
        },
        fields=["debit", "credit", "debit_in_account_currency",
                "credit_in_account_currency"],
    )
    if not entries:
        return None
    if len(entries) == 1:
        return entries[0]

    want_debit = row.income_flag == "true"
    for entry in entries:
        if want_debit and flt(entry.debit):
            return entry
        if not want_debit and flt(entry.credit):
            return entry
    return None
