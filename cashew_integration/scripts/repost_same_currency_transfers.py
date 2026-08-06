"""
Repost transfers between two same-currency foreign accounts that were booked at
exchange rate 1.0.

The old posting engine took a 1:1 shortcut whenever both legs shared a currency.
That is correct when the shared currency *is* the company currency, and wrong
otherwise: a USD amount went straight into a PKR column. The account stays
correct in its own currency and acquires a permanent phantom balance in company
currency — Elevate Pay was flat at 0.00 USD and -1,238.85 PKR for exactly this
reason.

The posting engine now looks the rate up and errors the row when none exists.
This repairs entries already in the ledger.

This script writes GL, so it never runs from a migration. Dry run first::

    bench --site <site> execute \\
      cashew_integration.scripts.repost_same_currency_transfers.run

Then apply::

    bench --site <site> execute \\
      cashew_integration.scripts.repost_same_currency_transfers.run \\
      --kwargs "{'apply': True}"
"""

import frappe
from frappe.utils import flt

from cashew_integration.importer.mapping import _lookup_erp_rate
from cashew_integration.importer.posting import post_transfer_pair
from cashew_integration.importer.worker import _row_to_dict


def run(apply: bool = False, company: str | None = None):
    """Find and optionally repost mis-rated same-currency foreign transfers."""
    affected = _find_affected(company)

    if not affected:
        print("cashew: no same-currency foreign transfers booked at rate 1.0")
        return []

    for case in affected:
        print(
            f"  {case['journal_entry']}  {case['posting_date']}  "
            f"{case['currency']} {case['amount']}  "
            f"booked {case['booked_base']} {case['company_currency']}, "
            f"should be ~{case['correct_base']}  (rate {case['rate']})"
        )

    if not apply:
        print(f"cashew: {len(affected)} entry(s) would be reposted. "
              "Re-run with --kwargs \"{'apply': True}\" to write.")
        return affected

    for case in affected:
        if not case["rate"]:
            print(f"  SKIP {case['journal_entry']}: no "
                  f"{case['currency']}->{case['company_currency']} rate on "
                  f"{case['posting_date']}. Create a Currency Exchange record first.")
            continue
        _repost(case)

    frappe.db.commit()
    return affected


def _find_affected(company: str | None) -> list[dict]:
    filters = {"txn_type": "Transfer", "posted_docname": ["is", "set"]}
    rows = frappe.get_all(
        "Cashew Import Row",
        filters=filters,
        fields=["name", "parent", "row_idx", "raw_amount", "source_currency",
                "posted_docname", "transfer_pair_row_idx", "income_flag",
                "resolved_erp_account"],
    )

    pairs: dict[tuple, list] = {}
    for row in rows:
        pairs.setdefault((row.parent, row.posted_docname), []).append(row)

    affected = []
    for (run_name, je_name), legs in sorted(pairs.items()):
        currencies = {leg.source_currency for leg in legs}
        if len(currencies) != 1:
            continue
        currency = currencies.pop()

        run_company = frappe.db.get_value("Cashew Import Run", run_name, "company")
        if company and run_company != company:
            continue
        company_currency = frappe.get_cached_value(
            "Company", run_company, "default_currency"
        )
        if currency == company_currency:
            continue

        docstatus, posting_date = frappe.db.get_value(
            "Journal Entry", je_name, ["docstatus", "posting_date"]
        )
        if docstatus != 1:
            continue

        booked = flt(frappe.db.get_value("Journal Entry", je_name, "total_debit"))
        amount = flt(legs[0].raw_amount)
        rate = _lookup_erp_rate(currency, company_currency, posting_date)

        # Already correct (posted after the fix, or manually repaired).
        if amount and abs(booked / amount - 1) > 0.01:
            continue

        affected.append({
            "run": run_name,
            "company": run_company,
            "journal_entry": je_name,
            "posting_date": posting_date,
            "currency": currency,
            "company_currency": company_currency,
            "amount": amount,
            "booked_base": round(booked, 2),
            "rate": rate,
            "correct_base": round(amount * rate, 2) if rate else None,
            "row_names": [leg.name for leg in legs],
            "row_indices": sorted(leg.row_idx for leg in legs),
        })

    return affected


def _repost(case: dict) -> None:
    run = frappe.get_doc("Cashew Import Run", case["run"])
    legs = [r for r in run.import_rows if r.row_idx in case["row_indices"]]
    if len(legs) != 2:
        print(f"  SKIP {case['journal_entry']}: expected 2 legs, found {len(legs)}")
        return

    source_row, dest_row = (_row_to_dict(leg) for leg in legs)
    if source_row.get("income_flag") == "true":
        source_row, dest_row = dest_row, source_row

    # Our own cancel — not an external one.
    frappe.flags.cashew_reverting = case["run"]
    try:
        old = frappe.get_doc("Journal Entry", case["journal_entry"])
        old.cancel()
    finally:
        frappe.flags.cashew_reverting = None

    doctype, docname = post_transfer_pair(source_row, dest_row, run)
    if not doctype:
        print(f"  FAILED {case['journal_entry']}: "
              f"{source_row.get('validation_error_message')}")
        return

    for leg, row in zip(legs, (source_row, dest_row)):
        frappe.db.set_value("Cashew Import Row", leg.name, {
            "posted_doctype": doctype,
            "posted_docname": docname,
            "exchange_rate": row.get("exchange_rate"),
            "base_amount": row.get("base_amount"),
            "revert_status": None,
            "revert_error": None,
        }, update_modified=False)

    print(f"  {case['journal_entry']} cancelled, reposted as {docname} "
          f"at rate {case['rate']}")
