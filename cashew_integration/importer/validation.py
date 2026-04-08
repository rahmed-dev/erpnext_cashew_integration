"""
C004 — Validation Engine

Two passes:

1. Queue-time row validation — called before the async worker starts.
   Validates every row that survived pre-preview (status != Error) and
   blocks those that still fail queue-time rules.

2. Run-level config check — validates run-level required fields before
   any rows are posted; raises immediately if run config is incomplete.

Transfer pairs are treated atomically: if either leg fails queue-time
validation, both legs are blocked.

All row errors are stored in-place (validation_status/error_code/message).
Run-config failure raises frappe.ValidationError with code RUN_CONFIG_MISSING.
"""

import frappe


# ── queue-time entry points ────────────────────────────────────────────────────

def validate_run_config(run, rows: list[dict]) -> None:
    """
    Raise ``frappe.ValidationError`` (RUN_CONFIG_MISSING) if any run-level
    required field is missing given the content of *rows*.

    Must be called before enqueuing the worker.
    """
    has_adjustment = any(r.get("txn_type") == "Adjustment" for r in rows
                         if r.get("validation_status") == "Valid")

    errors = []

    if not _company_default_cost_center(run.company):
        errors.append("Company default cost center is not set.")

    if has_adjustment and not run.balance_adjustment_account:
        errors.append(
            "File contains Adjustment rows but 'Balance Adjustment Account' is not set on the run."
        )

    if errors:
        frappe.throw(
            "Run configuration is incomplete:\n" + "\n".join(f"• {e}" for e in errors),
            frappe.ValidationError,
            title="RUN_CONFIG_MISSING",
        )


def validate_rows_at_queue_time(rows: list[dict]) -> None:
    """
    Apply all queue-time validation rules to *rows*.
    Mutates rows in-place. Transfer pairs are blocked atomically.
    """
    # First pass: validate each row individually
    for row in rows:
        if row.get("validation_status") == "Error":
            continue   # already blocked at pre-preview
        if row.get("validation_status") == "Skipped":
            continue   # idempotency guard already handled
        _validate_single_row(row)

    # Second pass: propagate errors across transfer pairs atomically
    _propagate_transfer_pair_errors(rows)


# ── per-row rules ──────────────────────────────────────────────────────────────

def _validate_single_row(row: dict) -> None:
    route   = row.get("resolved_route", "")
    txn_type = row.get("txn_type", "")

    # MAPPING_NOT_FOUND — non-Transfer, non-Adjustment rows with no route/account
    if txn_type not in ("Transfer", "External Transfer", "Adjustment"):
        if not route:
            _error(row, "MAPPING_NOT_FOUND",
                   f"No category mapping found for '{row['category']}' / "
                   f"'{row.get('sub_category', '')}' and no preview override was set.")
            return
        if not row.get("resolved_account"):
            _error(row, "MAPPING_NOT_FOUND",
                   "Resolved account is missing; set it in the preview before queueing.")
            return

    # INVALID_ACCOUNT_TYPE — resolved_account type must match route
    if route in ("Sales Invoice",) and row.get("resolved_account"):
        if not _account_is_type(row["resolved_account"], "Income"):
            _error(row, "INVALID_ACCOUNT_TYPE",
                   f"Account '{row['resolved_account']}' is not an Income account "
                   f"(required for Sales Invoice).")
            return

    if route in ("Purchase Invoice", "Journal Entry") and row.get("resolved_account"):
        if not _account_is_type(row["resolved_account"], "Expense"):
            _error(row, "INVALID_ACCOUNT_TYPE",
                   f"Account '{row['resolved_account']}' is not an Expense account "
                   f"(required for {route}).")
            return

    # PARTY_UNRESOLVED — SI/PI rows must have a party at queue time
    if route in ("Sales Invoice", "Purchase Invoice"):
        if not row.get("resolved_party"):
            _error(row, "PARTY_UNRESOLVED",
                   f"Party is required for {route} but has not been set. "
                   "Add a per-row override or set a run-level default.")
            return

    # EXCHANGE_RATE_MISSING / EXCHANGE_RATE_INVALID
    src_cur  = row.get("source_currency", "")
    cmp_cur  = row.get("company_currency", "")
    if src_cur != cmp_cur and txn_type not in ("Transfer", "External Transfer"):
        exr = row.get("exchange_rate")
        if not exr:
            _error(row, "EXCHANGE_RATE_MISSING",
                   "Exchange rate is required for foreign-currency rows "
                   "but has not been set.")
            return
        base = row.get("raw_amount", 0) * exr
        if not (base > 0):
            _error(row, "EXCHANGE_RATE_INVALID",
                   f"Exchange rate {exr} produces an invalid base amount ({base}).")
            return
        # update base_amount with confirmed rate
        row["base_amount"] = round(base, 2)


# ── transfer pair atomicity ────────────────────────────────────────────────────

def _propagate_transfer_pair_errors(rows: list[dict]) -> None:
    """If one leg of a transfer pair has an error, block the other leg too."""
    by_idx = {r["row_idx"]: r for r in rows}
    for row in rows:
        if row.get("txn_type") == "Transfer" and row.get("validation_status") == "Error":
            partner_idx = row.get("transfer_pair_row_idx")
            if partner_idx:
                partner = by_idx.get(partner_idx)
                if partner and partner.get("validation_status") != "Error":
                    _error(partner, row["validation_error_code"],
                           f"Partner leg (row {row['row_idx']}) has an error: "
                           f"{row['validation_error_message']}")


# ── account type helper ────────────────────────────────────────────────────────

def _account_is_type(account_name: str, root_type: str) -> bool:
    """Return True if the account's root_type matches (case-insensitive)."""
    try:
        rt = frappe.get_cached_value("Account", account_name, "root_type")
        return (rt or "").lower() == root_type.lower()
    except Exception:
        return True  # if lookup fails, don't block; let ERPNext surface the error at posting


# ── cost-center helper ─────────────────────────────────────────────────────────

def _company_default_cost_center(company: str) -> str | None:
    try:
        return frappe.get_cached_value("Company", company, "cost_center")
    except Exception:
        return None


# ── error helper ───────────────────────────────────────────────────────────────

def _error(row: dict, code: str, message: str) -> None:
    row["validation_status"]       = "Error"
    row["validation_error_code"]   = code
    row["validation_error_message"] = message
