"""
C005 — Posting Engine

Routes each valid, non-skipped row to the correct ERPNext document:
  1. Income / Expense  → Journal Entry (party on account line if requires_party)
  2. Transfer          → Transfer Journal Entry (one JE per pair)
  3. External Transfer → External Transfer JE
  4. Adjustment        → Adjustment JE

Each poster returns (posted_doctype, posted_docname).
Callers must wrap individual rows in try/except and record per-row failures.
"""

import frappe
from frappe.utils import flt


# ── public dispatcher ──────────────────────────────────────────────────────────

def post_row(row: dict, run) -> tuple[str, str]:
    """
    Post *row* and return ``(posted_doctype, posted_docname)``.

    Raises on any ERPNext error; caller handles and marks row Failed.
    """
    company_currency = frappe.get_cached_value("Company", run.company, "default_currency")
    cost_center      = frappe.get_cached_value("Company", run.company, "cost_center")
    route = row["resolved_route"]

    if route == "Journal Entry":
        return _post_journal_entry(row, run)
    if route == "Transfer JV":
        return _post_transfer_jv(row, run)
    if route == "External Transfer JE":
        return _post_external_transfer_je(row, run)
    if route == "Adjustment JE":
        return _post_adjustment_je(row, run)

    frappe.throw(f"Unknown resolved_route '{route}' on row {row['row_idx']}.")


# ── 1. Journal Entry (all income / expense) ───────────────────────────────────

def _post_journal_entry(row: dict, run):
    exr        = flt(row["exchange_rate"] or 1)
    src_cur    = row["source_currency"]
    cmp_cur    = frappe.get_cached_value("Company", run.company, "default_currency")
    multi_curr = 1 if src_cur != cmp_cur else 0
    base_amt   = flt(row.get("base_amount") or round(row["raw_amount"] * exr, 2))

    # resolved_account is the expense/income account (usually PKR).
    # We must use its real account_currency so Frappe's base-amount maths work.
    cat_cur = _get_account_currency(row["resolved_account"], run.company)
    cat_exr = 1.0 if cat_cur == cmp_cur else exr
    # If the category account is company-currency, record the PKR base amount;
    # otherwise record the raw foreign amount and let the exchange_rate convert it.
    cat_amt = base_amt if cat_cur == cmp_cur else row["raw_amount"]

    is_expense = row.get("txn_type") == "Expense"
    if is_expense:
        # Expense: debit expense account, credit bank (NSave)
        cat_dr,  cat_cr  = cat_amt,          0
        bank_dr, bank_cr = 0,                row["raw_amount"]
    else:
        # Income: debit bank (NSave), credit income account
        cat_dr,  cat_cr  = 0,                cat_amt
        bank_dr, bank_cr = row["raw_amount"], 0

    # Party on the expense/income leg when category requires it
    party_type = row.get("resolved_party_type") or None
    party      = row.get("resolved_party") or None
    has_party  = bool(row.get("requires_party") and party)

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
                "account":                    row["resolved_account"],
                "debit_in_account_currency":  cat_dr,
                "credit_in_account_currency": cat_cr,
                "exchange_rate":              cat_exr,
                "account_currency":           cat_cur,
                **({"party_type": party_type, "party": party} if has_party else {}),
            },
            {
                "account":                    row["resolved_erp_account"],
                "debit_in_account_currency":  bank_dr,
                "credit_in_account_currency": bank_cr,
                "exchange_rate":              exr,
                "account_currency":           src_cur,
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
        # same-currency: simple 1:1, base == account-currency amount.
        # Assumes at least one leg is in company currency (the f001 spec scope).
        # If both legs are foreign (e.g. USD→USD, company PKR) base amounts
        # would be wrong; guard this path before extending to that scenario.
        src_exr   = 1.0
        dst_exr   = 1.0
        src_base  = src_amount
        dst_base  = dst_amount
    else:
        src_exr, dst_exr, src_base, dst_base = _compute_implied_rates(
            src_cur, dst_cur, cmp_cur, src_amount, dst_amount, source_row["txn_date"]
        )

    imbalance = abs(dst_base - src_base)
    tolerance = flt(run.je_rounding_tolerance or 0.01)
    if imbalance > tolerance:
        _mark_transfer_pair_imbalance(source_row, dest_row, imbalance, tolerance)
        return "", ""

    src_name, dst_name = _extract_transfer_labels(
        source_row["note"], source_row["raw_account"], dest_row["raw_account"]
    )

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


def _compute_implied_rates(src_cur, dst_cur, cmp_cur, src_amount, dst_amount, txn_date):
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
        # Both foreign: convert dest via ERP rate on the transaction date
        from cashew_integration.importer.mapping import _lookup_erp_rate
        dst_erp_rate = _lookup_erp_rate(dst_cur, cmp_cur, txn_date) or 1.0
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


def _extract_transfer_labels(note: str, source_fallback: str, dest_fallback: str) -> tuple[str, str]:
    """Return (source_label, dest_label) extracted from a Transferred Balance note."""
    import re
    m = re.match(r"^Transferred Balance\n(.+)\s→\s(.+)$", note, re.DOTALL)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return source_fallback, dest_fallback


# ── 5. External Transfer JE ────────────────────────────────────────────────────

def _post_external_transfer_je(row: dict, run):
    src_cur    = row["source_currency"]
    cmp_cur    = frappe.get_cached_value("Company", run.company, "default_currency")
    exr        = flt(row.get("exchange_rate") or 1)
    multi_curr = 1 if src_cur != cmp_cur else 0

    note = row.get("note", "")
    src_label, dst_label = _extract_transfer_labels(note, row["raw_account"], "External")

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
        "multi_currency":    multi_curr,
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
    base_amt   = flt(row.get("base_amount") or round(row["raw_amount"] * exr, 2))
    income     = row.get("income_flag") == "true"

    # balance_adjustment_account is usually a PKR account — look up its real currency.
    adj_cur = _get_account_currency(run.balance_adjustment_account, run.company)
    adj_exr = 1.0 if adj_cur == cmp_cur else exr
    adj_amt = base_amt if adj_cur == cmp_cur else row["raw_amount"]

    # income=true : bank Debit, adjustment Credit
    # income=false: bank Credit, adjustment Debit
    my_debit  = row["raw_amount"] if income     else 0
    my_credit = 0                 if income     else row["raw_amount"]
    adj_debit  = 0                if income     else adj_amt
    adj_credit = adj_amt          if income     else 0

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
                "exchange_rate":              adj_exr,
                "account_currency":           adj_cur,
            },
        ],
    })
    je.insert()
    je.submit()
    return "Journal Entry", je.name



def _get_account_currency(account_name: str, company: str) -> str:
    cur = frappe.get_cached_value("Account", account_name, "account_currency")
    if cur:
        return cur
    return frappe.get_cached_value("Company", company, "default_currency")
