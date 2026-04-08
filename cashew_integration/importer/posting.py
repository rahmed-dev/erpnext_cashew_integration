"""
C005 — Posting Engine

Routes each valid, non-skipped row to the correct ERPNext document:
  1. Income        → Sales Invoice  (+ Payment Entry if auto_settle_cash)
  2. Expense > threshold → Purchase Invoice (+ Payment Entry)
  3. Expense ≤ threshold → Journal Entry
  4. Transfer      → Transfer Journal Entry (one JE per pair)
  5. External Transfer → External Transfer JE
  6. Adjustment    → Adjustment JE

Each poster returns (posted_doctype, posted_docname).
Callers must wrap individual rows in try/except and record per-row failures.
"""

import frappe
from frappe.utils import flt, today


# ── public dispatcher ──────────────────────────────────────────────────────────

def post_row(row: dict, run) -> tuple[str, str]:
    """
    Post *row* and return ``(posted_doctype, posted_docname)``.

    Raises on any ERPNext error; caller handles and marks row Failed.
    """
    company_currency = frappe.get_cached_value("Company", run.company, "default_currency")
    cost_center      = frappe.get_cached_value("Company", run.company, "cost_center")
    route = row["resolved_route"]

    if route == "Sales Invoice":
        return _post_sales_invoice(row, run, company_currency, cost_center)
    if route == "Purchase Invoice":
        return _post_purchase_invoice(row, run, company_currency, cost_center)
    if route == "Journal Entry":
        return _post_journal_entry(row, run)
    if route == "Transfer JV":
        return _post_transfer_jv(row, run)
    if route == "External Transfer JE":
        return _post_external_transfer_je(row, run)
    if route == "Adjustment JE":
        return _post_adjustment_je(row, run)

    frappe.throw(f"Unknown resolved_route '{route}' on row {row['row_idx']}.")


# ── 1. Sales Invoice ───────────────────────────────────────────────────────────

def _post_sales_invoice(row: dict, run, company_currency: str, cost_center: str):
    si = frappe.get_doc({
        "doctype":             "Sales Invoice",
        "company":             run.company,
        "customer":            row["resolved_party"],
        "posting_date":        row["txn_date"],
        "due_date":            row["txn_date"],
        "currency":            row["source_currency"],
        "conversion_rate":     flt(row["exchange_rate"] or 1),
        "ignore_pricing_rule": 1,
        "taxes_and_charges":   None,
        "cashew_import_run":   run.name,
        "cashew_row_hash":     row["source_hash"],
        "cashew_row_idx":      row["row_idx"],
        "items": [{
            "item_name":      row["item_label"],
            "qty":            1,
            "rate":           row["raw_amount"],
            "income_account": row["resolved_account"],
            "cost_center":    cost_center,
        }],
    })
    si.flags.ignore_permissions = False
    si.insert()
    si.submit()

    if run.auto_settle_cash:
        _create_payment_entry(si, "Receive", run, row)

    return "Sales Invoice", si.name


# ── 2. Purchase Invoice ────────────────────────────────────────────────────────

def _post_purchase_invoice(row: dict, run, company_currency: str, cost_center: str):
    pi = frappe.get_doc({
        "doctype":             "Purchase Invoice",
        "company":             run.company,
        "supplier":            row["resolved_party"],
        "posting_date":        row["txn_date"],
        "due_date":            row["txn_date"],
        "currency":            row["source_currency"],
        "conversion_rate":     flt(row["exchange_rate"] or 1),
        "ignore_pricing_rule": 1,
        "taxes_and_charges":   None,
        "cashew_import_run":   run.name,
        "cashew_row_hash":     row["source_hash"],
        "cashew_row_idx":      row["row_idx"],
        "items": [{
            "item_name":       row["item_label"],
            "qty":             1,
            "rate":            row["raw_amount"],
            "expense_account": row["resolved_account"],
            "cost_center":     cost_center,
        }],
    })
    pi.flags.ignore_permissions = False
    pi.insert()
    pi.submit()

    if run.auto_settle_cash:
        _create_payment_entry(pi, "Pay", run, row)

    return "Purchase Invoice", pi.name


# ── 3. Journal Entry (small expense) ──────────────────────────────────────────

def _post_journal_entry(row: dict, run):
    exr         = flt(row["exchange_rate"] or 1)
    src_cur     = row["source_currency"]
    cmp_cur     = frappe.get_cached_value("Company", run.company, "default_currency")
    multi_curr  = 1 if src_cur != cmp_cur else 0

    je = frappe.get_doc({
        "doctype":            "Journal Entry",
        "company":            run.company,
        "posting_date":       row["txn_date"],
        "multi_currency":     multi_curr,
        "remark":             (
            f"Cashew Import: {row['category']} | {row.get('title','')} | "
            f"{row['month_key']} | run:{run.name}"
        ),
        "cashew_import_run":  run.name,
        "cashew_row_hash":    row["source_hash"],
        "cashew_row_idx":     row["row_idx"],
        "accounts": [
            {
                "account":                         row["resolved_account"],
                "debit_in_account_currency":       row["raw_amount"],
                "credit_in_account_currency":      0,
                "exchange_rate":                   exr,
                "account_currency":                src_cur,
            },
            {
                "account":                         row["resolved_erp_account"],
                "debit_in_account_currency":       0,
                "credit_in_account_currency":      row["raw_amount"],
                "exchange_rate":                   exr,
                "account_currency":                src_cur,
            },
        ],
    })
    je.insert()
    je.submit()
    return "Journal Entry", je.name


# ── 4. Transfer JV (paired internal transfer) ─────────────────────────────────

def post_transfer_pair(source_row: dict, dest_row: dict, run) -> tuple[str, str]:
    """
    Create one Transfer JV for a paired transfer.
    Called by the async worker when it encounters the second leg of a pair.
    Returns (doctype, docname) stored on both legs.
    """
    cmp_cur       = frappe.get_cached_value("Company", run.company, "default_currency")
    src_cur       = source_row["source_currency"]
    dst_cur       = dest_row["source_currency"]
    src_amount    = source_row["raw_amount"]
    dst_amount    = dest_row["raw_amount"]
    multi_curr    = 1 if (src_cur != cmp_cur or dst_cur != cmp_cur) else 0

    if src_cur == dst_cur:
        # same-currency: simple 1:1
        src_exr   = 1.0
        dst_exr   = 1.0
        src_base  = src_amount
        dst_base  = dst_amount
    else:
        src_exr, dst_exr, src_base, dst_base = _compute_implied_rates(
            src_cur, dst_cur, cmp_cur, src_amount, dst_amount, run
        )

    imbalance = abs(dst_base - src_base)
    tolerance = flt(run.je_rounding_tolerance or 0.01)
    if imbalance > tolerance:
        _mark_transfer_pair_imbalance(source_row, dest_row, imbalance, tolerance)
        return "", ""

    src_name = _extract_account_name_from_note(source_row["note"], source_row["raw_account"])
    dst_name = _extract_account_name_from_note(source_row["note"], dest_row["raw_account"])

    je = frappe.get_doc({
        "doctype":           "Journal Entry",
        "company":           run.company,
        "posting_date":      source_row["txn_date"],
        "multi_currency":    multi_curr,
        "remark":            (
            f"Cashew Transfer: {src_name} → {dst_name} | "
            f"{src_amount} {src_cur} → {dst_amount} {dst_cur} | run:{run.name}"
        ),
        "cashew_import_run": run.name,
        "cashew_row_hash":   source_row["source_hash"],
        "cashew_row_idx":    source_row["row_idx"],
        "accounts": [
            {
                "account":                    dest_row["resolved_erp_account"],
                "debit_in_account_currency":  dst_amount,
                "credit_in_account_currency": 0,
                "exchange_rate":              dst_exr,
                "account_currency":           dst_cur,
                "debit":                      dst_base,
            },
            {
                "account":                    source_row["resolved_erp_account"],
                "debit_in_account_currency":  0,
                "credit_in_account_currency": src_amount,
                "exchange_rate":              src_exr,
                "account_currency":           src_cur,
                "credit":                     src_base,
            },
        ],
    })
    je.insert()
    je.submit()
    return "Journal Entry", je.name


def _compute_implied_rates(src_cur, dst_cur, cmp_cur, src_amount, dst_amount, run):
    """Compute implied exchange rates ensuring the JV balances in company currency."""
    if dst_cur == cmp_cur:
        dst_base    = dst_amount
        dst_exr     = 1.0
        implied     = dst_base / src_amount
        src_base    = round(src_amount * implied, 2)
        src_exr     = implied
    elif src_cur == cmp_cur:
        src_base    = src_amount
        src_exr     = 1.0
        implied     = src_amount / dst_amount
        dst_base    = round(dst_amount * implied, 2)
        dst_exr     = implied
    else:
        # Both foreign: convert dest via ERP rate
        from cashew_integration.importer.mapping import _lookup_erp_rate
        dst_erp_rate = _lookup_erp_rate(dst_cur, cmp_cur, run.posting_date or today()) or 1.0
        dst_base     = round(dst_amount * dst_erp_rate, 2)
        dst_exr      = dst_erp_rate
        implied      = dst_base / src_amount
        src_base     = round(src_amount * implied, 2)
        src_exr      = implied

    return src_exr, dst_exr, src_base, dst_base


def _mark_transfer_pair_imbalance(source_row, dest_row, imbalance, tolerance):
    msg = (
        f"Transfer JV imbalance {imbalance} exceeds tolerance {tolerance}. "
        "Adjust the exchange rate in the preview or increase JV Rounding Tolerance."
    )
    for r in (source_row, dest_row):
        r["validation_status"]        = "Error"
        r["validation_error_code"]    = "TRANSFER_JV_IMBALANCE"
        r["validation_error_message"] = msg


def _extract_account_name_from_note(note: str, fallback: str) -> str:
    import re
    m = re.match(r"^Transferred Balance\n(.+)\s→\s(.+)$", note, re.DOTALL)
    if m:
        return f"{m.group(1).strip()} → {m.group(2).strip()}"
    return fallback


# ── 5. External Transfer JE ────────────────────────────────────────────────────

def _post_external_transfer_je(row: dict, run):
    src_cur = row["source_currency"]
    exr     = flt(row.get("exchange_rate") or 1)

    import re
    note   = row.get("note", "")
    m      = re.match(r"^Transferred Balance\n(.+)\s→\s(.+)$", note, re.DOTALL)
    src_label = m.group(1).strip() if m else row["raw_account"]
    dst_label = m.group(2).strip() if m else "External"

    income = row.get("income_flag") == "true"
    if income:
        # money arrived: external → my account
        debit_acct  = row["resolved_erp_account"]
        credit_acct = row["resolved_external_account"]
    else:
        # money left: my account → external
        debit_acct  = row["resolved_external_account"]
        credit_acct = row["resolved_erp_account"]

    je = frappe.get_doc({
        "doctype":           "Journal Entry",
        "company":           run.company,
        "posting_date":      row["txn_date"],
        "multi_currency":    0,
        "remark":            (
            f"Cashew External Transfer: {src_label} → {dst_label} | "
            f"{row['raw_amount']} {src_cur} | run:{run.name}"
        ),
        "cashew_import_run": run.name,
        "cashew_row_hash":   row["source_hash"],
        "cashew_row_idx":    row["row_idx"],
        "accounts": [
            {
                "account":                    debit_acct,
                "debit_in_account_currency":  row["raw_amount"],
                "credit_in_account_currency": 0,
                "exchange_rate":              exr,
                "account_currency":           src_cur,
            },
            {
                "account":                    credit_acct,
                "debit_in_account_currency":  0,
                "credit_in_account_currency": row["raw_amount"],
                "exchange_rate":              exr,
                "account_currency":           src_cur,
            },
        ],
    })
    je.insert()
    je.submit()
    return "Journal Entry", je.name


# ── 6. Adjustment JE ──────────────────────────────────────────────────────────

def _post_adjustment_je(row: dict, run):
    src_cur    = row["source_currency"]
    cmp_cur    = frappe.get_cached_value("Company", run.company, "default_currency")
    exr        = flt(row.get("exchange_rate") or 1)
    multi_curr = 1 if src_cur != cmp_cur else 0
    income     = row.get("income_flag") == "true"

    # income=true: my account Debit, adjustment Credit
    # income=false: my account Credit, adjustment Debit
    my_debit  = row["raw_amount"] if income  else 0
    my_credit = row["raw_amount"] if not income else 0
    adj_debit  = 0                 if income  else row["raw_amount"]
    adj_credit = row["raw_amount"] if income  else 0

    je = frappe.get_doc({
        "doctype":           "Journal Entry",
        "company":           run.company,
        "posting_date":      row["txn_date"],
        "multi_currency":    multi_curr,
        "remark":            (
            f"Cashew Adjustment: {row['raw_amount']} {src_cur} | "
            f"{row.get('note') or 'no note'} | run:{run.name} — Review Recommended"
        ),
        "cashew_import_run": run.name,
        "cashew_row_hash":   row["source_hash"],
        "cashew_row_idx":    row["row_idx"],
        "accounts": [
            {
                "account":                    row["resolved_erp_account"],
                "debit_in_account_currency":  my_debit,
                "credit_in_account_currency": my_credit,
                "exchange_rate":              exr,
                "account_currency":           src_cur,
            },
            {
                "account":                    run.balance_adjustment_account,
                "debit_in_account_currency":  adj_debit,
                "credit_in_account_currency": adj_credit,
                "exchange_rate":              exr,
                "account_currency":           src_cur,
            },
        ],
    })
    je.insert()
    je.submit()
    return "Journal Entry", je.name


# ── Payment Entry ──────────────────────────────────────────────────────────────

def _create_payment_entry(invoice, payment_type: str, run, row: dict):
    """Create and submit a Payment Entry linked to *invoice* to settle it immediately."""
    is_si = invoice.doctype == "Sales Invoice"

    pe = frappe.get_doc({
        "doctype":               "Payment Entry",
        "payment_type":          payment_type,
        "company":               run.company,
        "posting_date":          row["txn_date"],
        "mode_of_payment":       run.default_mode_of_payment,
        "party_type":            "Customer" if is_si else "Supplier",
        "party":                 invoice.customer if is_si else invoice.supplier,
        "paid_from":             invoice.debit_to if is_si else _get_mode_of_payment_account(run, is_si),
        "paid_to":               _get_mode_of_payment_account(run, is_si) if is_si else invoice.credit_to,
        "paid_amount":           invoice.grand_total,
        "received_amount":       invoice.grand_total,
        "source_exchange_rate":  flt(invoice.conversion_rate or 1),
        "target_exchange_rate":  flt(invoice.conversion_rate or 1),
        "paid_from_account_currency": invoice.currency,
        "paid_to_account_currency":   invoice.currency,
        "references": [{
            "reference_doctype": invoice.doctype,
            "reference_name":    invoice.name,
            "allocated_amount":  invoice.grand_total,
        }],
    })
    pe.insert()
    pe.submit()
    return pe.name


def _get_mode_of_payment_account(run, is_sales: bool) -> str:
    """Fetch the GL account linked to the run's default mode of payment."""
    mop = frappe.get_doc("Mode of Payment", run.default_mode_of_payment)
    company = run.company
    for acct in mop.accounts:
        if acct.company == company:
            return acct.default_account
    frappe.throw(
        f"Mode of Payment '{run.default_mode_of_payment}' has no account configured "
        f"for company '{company}'.",
        frappe.ValidationError,
    )
