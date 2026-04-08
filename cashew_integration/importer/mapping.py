"""
C003 — Mapping + Preview Override Engine

Reads Cashew Settings and resolves, for each parsed row:
  - resolved_erp_account     (Cashew Account Mapping lookup on raw_account)
  - resolved_external_account (External Transfer rows: partner account from mapping)
  - resolved_route / resolved_account (Category Mapping lookup, non-Transfer rows)
  - exchange_rate / base_amount  (ERP rate pre-fill for foreign-currency SI/PI/JE/Adjustment)
  - resolved_party / resolved_party_type / party_source (run-default fallback)

Transfer and External Transfer rows skip category and party resolution.
Adjustment rows skip category resolution (route already set by parser).

Designed to be called after parse_csv() and before the validation engine.
Mutates row dicts in-place; returns nothing.
"""

import frappe


# ── public entry point ─────────────────────────────────────────────────────────

def apply_mappings(rows: list[dict], run: "frappe.model.document.Document") -> None:
    """
    Resolve all mappings for *rows* using *run* context.

    *run* must have: ``company``, ``expense_threshold``,
    ``default_customer``, ``default_supplier``.
    """
    settings = frappe.get_single("Cashew Settings")
    company_currency = run.company_currency if hasattr(run, "company_currency") else \
        frappe.get_cached_value("Company", run.company, "default_currency")

    acct_map  = _build_account_map(settings)
    cat_map   = _build_category_map(settings)

    for row in rows:
        if row.get("validation_status") == "Error":
            continue  # pre-preview errors; skip further resolution

        _resolve_erp_account(row, acct_map)
        _resolve_category(row, cat_map)
        _resolve_exchange_rate(row, company_currency)
        _resolve_party(row, run)


# ── settings caches ────────────────────────────────────────────────────────────

def _build_account_map(settings) -> dict[str, dict]:
    """Return {cashew_account_name -> {erp_account, account_currency}} for active rows."""
    result = {}
    for row in settings.cashew_account_mapping or []:
        if row.is_active:
            result[row.cashew_account_name] = {
                "erp_account":      row.erp_account,
                "account_currency": row.account_currency,
            }
    return result


def _build_category_map(settings) -> dict[tuple, dict]:
    """Return {(cashew_category, sub_category) -> {default_route, default_account}}."""
    result = {}
    for row in settings.cashew_category_mapping or []:
        if row.is_active:
            key = (row.cashew_category, row.cashew_sub_category or "")
            result[key] = {
                "default_route":   row.default_route,
                "default_account": row.default_account,
            }
    return result


# ── account mapping ────────────────────────────────────────────────────────────

def _resolve_erp_account(row: dict, acct_map: dict) -> None:
    mapping = acct_map.get(row["raw_account"])
    if not mapping:
        row["validation_status"] = "Error"
        row["validation_error_code"] = "CASHEW_ACCOUNT_NOT_MAPPED"
        row["validation_error_message"] = (
            f"No active Cashew Account Mapping for account '{row['raw_account']}'."
        )
        return

    row["resolved_erp_account"] = mapping["erp_account"]

    # External Transfer: also resolve the partner account
    if row.get("txn_type") == "External Transfer":
        partner_name = _extract_partner_name(row)
        if partner_name:
            partner_mapping = acct_map.get(partner_name)
            if partner_mapping:
                row["resolved_external_account"] = partner_mapping["erp_account"]
            else:
                row["validation_status"] = "Error"
                row["validation_error_code"] = "EXTERNAL_ACCOUNT_NOT_MAPPED"
                row["validation_error_message"] = (
                    f"No active Cashew Account Mapping for external account '{partner_name}'."
                )


def _extract_partner_name(row: dict) -> str:
    """Parse the transfer note to get the partner account name."""
    import re
    note = row.get("note", "")
    m = re.match(r"^Transferred Balance\n(.+)\s→\s(.+)$", note, re.DOTALL)
    if not m:
        return ""
    source_name = m.group(1).strip()
    dest_name   = m.group(2).strip()
    if row["raw_account"] == source_name:
        return dest_name
    return source_name


# ── category mapping ───────────────────────────────────────────────────────────

def _resolve_category(row: dict, cat_map: dict) -> None:
    txn_type = row.get("txn_type", "")

    # Transfer, External Transfer, and Adjustment skip category lookup
    if txn_type in ("Transfer", "External Transfer", "Adjustment"):
        if txn_type == "Transfer":
            row.setdefault("resolved_route", "Transfer JV")
        elif txn_type == "External Transfer":
            row.setdefault("resolved_route", "External Transfer JE")
        # Adjustment route already set by parser
        return

    if row.get("validation_status") == "Error":
        return

    # Try (category, sub_category) then fall back to (category, "")
    cat  = row["category"]
    sub  = row.get("sub_category", "") or ""
    hit  = cat_map.get((cat, sub)) or cat_map.get((cat, ""))

    if hit:
        row.setdefault("resolved_route",   hit["default_route"])
        row.setdefault("resolved_account", hit["default_account"])
    # If no hit: row enters preview as unresolved; queue-time validation catches it


# ── exchange rate ──────────────────────────────────────────────────────────────

def _resolve_exchange_rate(row: dict, company_currency: str) -> None:
    if row.get("validation_status") == "Error":
        return

    src_cur = row.get("source_currency", "")

    # Same-currency: already set to 1 by parser
    if src_cur == company_currency:
        return

    # Transfer rows: implied rate is computed at posting time; do not pre-fill
    if row.get("txn_type") in ("Transfer", "External Transfer"):
        return

    # All other foreign-currency rows: attempt ERP rate lookup
    if not row.get("exchange_rate"):
        erp_rate = _lookup_erp_rate(src_cur, company_currency, row["txn_date"])
        if erp_rate:
            row["exchange_rate"] = erp_rate
            row["base_amount"]   = round(row["raw_amount"] * erp_rate, 2)
        # If not found: exchange_rate stays None; queue-time validation will catch it


def _lookup_erp_rate(from_currency: str, to_currency: str, date: str):
    """
    Look up the exchange rate from the ERPNext Currency Exchange master.
    Returns float or None.
    """
    try:
        from erpnext.setup.utils import get_exchange_rate
        rate = get_exchange_rate(from_currency, to_currency, date, args="for_buying")
        if rate and rate > 0:
            return float(rate)
    except Exception:
        pass
    return None


# ── party resolution ───────────────────────────────────────────────────────────

def _resolve_party(row: dict, run) -> None:
    if row.get("validation_status") == "Error":
        return

    route = row.get("resolved_route", "")
    if route not in ("Sales Invoice", "Purchase Invoice"):
        return

    # Per-row preview override takes precedence; only apply run default if unset
    if row.get("resolved_party"):
        if not row.get("party_source"):
            row["party_source"] = "Preview Override"
        return

    if route == "Sales Invoice" and run.default_customer:
        row["resolved_party"]      = run.default_customer
        row["resolved_party_type"] = "Customer"
        row["party_source"]        = "Run Default"
    elif route == "Purchase Invoice" and run.default_supplier:
        row["resolved_party"]      = run.default_supplier
        row["resolved_party_type"] = "Supplier"
        row["party_source"]        = "Run Default"
    # If still unresolved: queue-time validation will fire PARTY_UNRESOLVED
