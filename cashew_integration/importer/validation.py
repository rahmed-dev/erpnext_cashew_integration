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

from cashew_integration.importer.errors import set_row_validation_error


# ── queue-time entry points ────────────────────────────────────────────────────

def validate_run_config(run, rows: list[dict]) -> None:
    """
    Raise ``frappe.ValidationError`` (RUN_CONFIG_MISSING) if any run-level
    required field is missing given the content of *rows*.

    Must be called before enqueuing the worker.
    """
    errors = get_run_config_errors(run, rows)
    if errors:
        frappe.throw(
            "Run configuration is incomplete:\n" + "\n".join(f"• {e}" for e in errors),
            frappe.ValidationError,
            title="RUN_CONFIG_MISSING",
        )


def get_run_config_errors(run, rows: list[dict]) -> list[str]:
    """
    Return run-level config gaps for the current row set without raising.
    """
    has_adjustment = any(
        r.get("txn_type") == "Adjustment" for r in rows
        if r.get("validation_status") == "Valid"
    )

    errors = []
    if not _company_default_cost_center(run.company):
        errors.append("Company default cost center is not set.")

    if has_adjustment and not run.balance_adjustment_account:
        errors.append(
            "File contains Adjustment rows but 'Balance Adjustment Account' is not set on the run."
        )
    if run.balance_adjustment_account and _account_is_group(run.balance_adjustment_account):
        errors.append(
            f"Balance Adjustment Account '{run.balance_adjustment_account}' is a Group account "
            "and cannot be used in transactions. Select a leaf account instead."
        )
    return errors


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

    # CATEGORY_ACCOUNT_CLASS_MISMATCH — mapping's default_account class must match
    # its declared category_type. Catches mapping drift (e.g. Income mapping
    # repointed to an Expense account post-save). Transfer-family bypasses.
    if txn_type not in ("Transfer", "External Transfer", "Adjustment"):
        mapping = _category_mapping_for(row.get("category"), row.get("sub_category"))
        if mapping:
            msg = check_category_account_class(
                mapping.get("category_type"), mapping.get("default_account")
            )
            if msg:
                _error(row, "CATEGORY_ACCOUNT_CLASS_MISMATCH", msg)
                return

    # GROUP_ACCOUNT — group accounts cannot be used in transactions
    for acct_field in ("resolved_account", "resolved_erp_account", "resolved_external_account"):
        acct = row.get(acct_field)
        if acct and _account_is_group(acct):
            _error(row, "GROUP_ACCOUNT",
                   f"Account '{acct}' is a Group account and cannot be used in transactions. "
                   "Select a leaf (posting) account instead.")
            return

    # INVALID_ACCOUNT_TYPE — resolved_account type must match transaction type
    if row.get("resolved_account") and route == "Journal Entry":
        txn_type = row.get("txn_type", "")
        if txn_type == "Income" and not _account_is_type(row["resolved_account"], "Income"):
            _error(row, "INVALID_ACCOUNT_TYPE",
                   f"Account '{row['resolved_account']}' is not an Income account "
                   "(required for Income rows).")
            return
        if txn_type == "Expense" and not _account_is_type(row["resolved_account"], "Expense"):
            _error(row, "INVALID_ACCOUNT_TYPE",
                   f"Account '{row['resolved_account']}' is not an Expense account "
                   "(required for Expense rows).")
            return

    # PARTY_MISSING / LOAN_PARTY_MISSING — c003 split. Loan rows always require
    # a party (hardcoded from Decision 1); Income/Expense rows defer to the
    # category's requires_party flag.
    validate_party_present(row)
    if row.get("validation_status") == "Error":
        return

    # EXCHANGE_RATE_MISSING / EXCHANGE_RATE_INVALID
    src_cur  = row.get("source_currency", "")
    cmp_cur  = row.get("company_currency", "")
    if src_cur != cmp_cur and txn_type != "Transfer":
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


# ── party presence (c003) ──────────────────────────────────────────────────────

def validate_party_present(row: dict) -> None:
    """Set a row-level error when a party is required but ``resolved_party``
    is empty. Two error codes:

    - ``LOAN_PARTY_MISSING`` for Loan Receivable / Loan Payable rows (party
      requirement is hardcoded from f006 Decision 1, independent of
      ``requires_party`` flag).
    - ``PARTY_MISSING`` for Income / Expense rows whose category mapping
      sets ``requires_party=1``.

    Transfer-family rows are skipped — they don't carry a party.
    """
    txn_type = row.get("txn_type", "")
    if txn_type in ("Transfer", "External Transfer", "Adjustment"):
        return

    if txn_type in ("Loan Receivable", "Loan Payable"):
        if not row.get("resolved_party"):
            expected = "Customer" if txn_type == "Loan Receivable" else "Supplier"
            set_row_validation_error(
                row, "LOAN_PARTY_MISSING",
                f"{txn_type} row requires a {expected} party. "
                "Set party in Row Explorer.",
            )
        return

    if row.get("requires_party") and not row.get("resolved_party"):
        expected = "Customer" if txn_type == "Income" else "Supplier"
        set_row_validation_error(
            row, "PARTY_MISSING",
            f"This {txn_type} category requires a {expected} party. "
            "Set party in Row Explorer.",
        )


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

def _account_is_group(account_name: str) -> bool:
    """Return True if the account is a Group (cannot post transactions to it)."""
    try:
        return bool(frappe.get_cached_value("Account", account_name, "is_group"))
    except Exception:
        return False  # if lookup fails, allow through; ERPNext will surface it at posting


def _account_is_type(account_name: str, root_type: str) -> bool:
    """Return True if the account's root_type matches (case-insensitive)."""
    try:
        rt = frappe.get_cached_value("Account", account_name, "root_type")
        return (rt or "").lower() == root_type.lower()
    except Exception:
        return True  # if lookup fails, don't block; let ERPNext surface the error at posting


# ── category-type / account-class predicate ────────────────────────────────────
#
# Single source of truth used by:
#   - CashewCategoryMapping.validate (save-time, in cashew_category_mapping.py)
#   - _validate_single_row (validate-time, per row)

_CATEGORY_TYPE_EXPECTATIONS = {
    "Income":   ("Income",    None),
    "Expense":  ("Expense",   None),
    "Loan Out": ("Asset",     "Receivable"),
    "Loan In":  ("Liability", "Payable"),
}


def check_category_account_class(category_type: str | None, account_name: str | None) -> str | None:
    """Return None if the account's class matches the category_type expectation;
    otherwise a friendly error message describing the mismatch.

    Skip (return None) when account_name is falsy — the required-field guard
    handles missing account elsewhere. Skip when category_type is unknown —
    other validators / required-field guards handle that case.
    """
    if not account_name:
        return None
    expected = _CATEGORY_TYPE_EXPECTATIONS.get(category_type or "")
    if not expected:
        return None
    expected_root, expected_type = expected
    try:
        acct = frappe.get_cached_value(
            "Account", account_name, ["root_type", "account_type"], as_dict=True
        )
    except Exception:
        return None  # lookup failure — don't block; ERPNext will surface at posting
    if not acct:
        return None
    actual_root = (acct.get("root_type") or "")
    actual_type = (acct.get("account_type") or "")
    root_ok = actual_root.lower() == expected_root.lower()
    type_ok = (expected_type is None) or (actual_type.lower() == expected_type.lower())
    if root_ok and type_ok:
        return None
    return (
        f"Account '{account_name}' has root_type '{actual_root}' / "
        f"account_type '{actual_type}', but category_type '{category_type}' "
        f"requires root_type '{expected_root}' / "
        f"account_type '{expected_type or '(any)'}'."
    )


def check_loan_account_class_exists(category_type: str | None) -> str | None:
    """Return None if at least one viable account exists in the chart for the
    given loan ``category_type`` (Loan Out / Loan In); a friendly setup-pointing
    error otherwise.

    Short-circuits for non-loan category_types (Income / Expense / unknown) —
    the chart-existence check only applies to Loan rows.

    Single-company assumption (Configuration Structure decision): query is
    unscoped across companies. Filters ``is_group=0`` and ``disabled=0`` to
    match the Account picker UX.
    """
    expected = _CATEGORY_TYPE_EXPECTATIONS.get(category_type or "")
    if not expected:
        return None
    expected_root, expected_type = expected
    if expected_type is None:
        return None  # Income / Expense — c008 doesn't apply

    try:
        exists = frappe.db.exists("Account", {
            "root_type":    expected_root,
            "account_type": expected_type,
            "is_group":     0,
            "disabled":     0,
        })
    except Exception:
        return None  # lookup failure — don't block save; ERPNext surfaces at posting
    if exists:
        return None

    sample = "Loan Receivable" if category_type == "Loan Out" else "Loan Payable"
    return (
        f"No {expected_type} account exists in your chart of accounts. "
        f"Create or configure an {expected_root} account with "
        f"account_type={expected_type} (e.g. '{sample} - <Co>') before mapping a "
        f"{category_type} category. See: Setup → Chart of Accounts."
    )


def _category_mapping_for(category: str | None, sub_category: str | None) -> dict | None:
    """Look up a Cashew Category Mapping entry by (category, sub_category) with
    fallback to (category, '') — same precedence as importer/mapping._build_category_map.
    Returns dict with category_type + default_account, or None if no match.

    Uses ``get_doc`` (uncached) instead of ``get_cached_doc`` so that mapping
    edits are picked up immediately on the next validate without waiting for a
    cache invalidation. Validation runs are infrequent, so the extra read cost
    per row is acceptable in exchange for guaranteed freshness.
    """
    if not category:
        return None
    try:
        settings = frappe.get_doc("Cashew Settings")
    except Exception:
        return None
    sub = sub_category or ""
    exact = None
    cat_only = None
    for m in settings.cashew_category_mapping or []:
        if m.cashew_category != category:
            continue
        if (m.cashew_sub_category or "") == sub:
            exact = m
            break
        if not (m.cashew_sub_category or ""):
            cat_only = m
    hit = exact or cat_only
    if not hit:
        return None
    return {
        "category_type": hit.category_type,
        "default_account": hit.default_account,
    }


# ── cost-center helper ─────────────────────────────────────────────────────────

def _company_default_cost_center(company: str) -> str | None:
    try:
        return frappe.get_cached_value("Company", company, "cost_center")
    except Exception:
        return None


# ── error helper ───────────────────────────────────────────────────────────────

def _error(row: dict, code: str, message: str) -> None:
    """Thin shim — delegates to shared helper which stamps `[Row N] ` prefix."""
    set_row_validation_error(row, code, message)
