"""
C003 — Mapping + Preview Override Engine

Reads Cashew Settings and resolves, for each parsed row:
  - resolved_erp_account     (Cashew Account Mapping lookup on raw_account)
  - resolved_external_account (External Transfer rows: partner account from mapping)
  - resolved_route / resolved_account (Category Mapping lookup, non-Transfer rows)
  - resolved_party_type (pre-filled from txn_type — derivable invariant; user
    picks the actual party in the Vue Row Explorer per f006 Decision 2)

Exchange-rate resolution is intentionally deferred — it is triggered explicitly
during the Validate Import stage (``apply_exchange_rates``) so online lookups
only fire when the user asks for them, not on every parse.

Transfer and External Transfer rows skip category and party resolution.
Adjustment rows skip category resolution (route already set by parser).

f006 Decision 2 (c003): no rule-based party resolution. Run-level
default_customer / default_supplier are no longer consulted; ``party_source``
is no longer written (column kept on doctype for f004 revert backward compat).

Designed to be called after parse_csv() and before the validation engine.
Mutates row dicts in-place; returns nothing.
"""

import frappe
import requests

from cashew_integration.importer.category_lookup import build_category_type_map
from cashew_integration.importer.errors import set_row_validation_error


# ── public entry point ─────────────────────────────────────────────────────────

def apply_mappings(rows: list[dict], run: "frappe.model.document.Document") -> None:
    """
    Resolve all mappings for *rows* using *run* context.

    *run* must have: ``company``, ``expense_threshold``.

    Note: ``default_customer`` / ``default_supplier`` columns survive on the
    doctype for f004 revert backward compat but are no longer consulted by
    this engine (f006 Decision 2 — no rule-based party resolution).
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
        _resolve_party(row, run)
        # Exchange-rate resolution is NOT done here.
        # Call apply_exchange_rates() separately at Validate Import time.


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
    """Return {(cashew_category, sub_category) -> {default_account, requires_party,
    category_type, is_active}}.

    Delegates to ``category_lookup.build_category_type_map`` so parser + mapping
    + validation share one source of truth (f006 c002). Downstream callers in
    this module read ``default_account`` and ``requires_party`` exactly as
    before; the additional keys are inert here.
    """
    return build_category_type_map()


# ── account mapping ────────────────────────────────────────────────────────────

def _resolve_erp_account(row: dict, acct_map: dict) -> None:
    mapping = acct_map.get(row["raw_account"])
    if not mapping:
        set_row_validation_error(
            row, "CASHEW_ACCOUNT_NOT_MAPPED",
            f"No active Cashew Account Mapping for account '{row['raw_account']}'.",
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
                set_row_validation_error(
                    row, "EXTERNAL_ACCOUNT_NOT_MAPPED",
                    f"No active Cashew Account Mapping for external account '{partner_name}'.",
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
        _set_income_expense_accounts(row)
        return

    if row.get("validation_status") == "Error":
        return

    # All income/expense rows go via Journal Entry.
    row.setdefault("resolved_route", "Journal Entry")

    # Try (category, sub_category) then fall back to (category, "")
    cat = row["category"]
    sub = row.get("sub_category", "") or ""
    hit = cat_map.get((cat, sub)) or cat_map.get((cat, ""))

    if hit:
        row.setdefault("resolved_account", hit["default_account"])
        row["requires_party"] = 1 if hit["requires_party"] else 0
    _set_income_expense_accounts(row)
    # If no hit: row enters preview as unresolved; queue-time validation catches it


def _set_income_expense_accounts(row: dict) -> None:
    """Expose explicit target account by posting type for UI clarity."""
    acct     = row.get("resolved_account")
    txn_type = row.get("txn_type", "")
    row["resolved_income_account"]  = None
    row["resolved_expense_account"] = None
    if not acct:
        return
    if txn_type == "Income":
        row["resolved_income_account"] = acct
    elif txn_type == "Expense":
        row["resolved_expense_account"] = acct


# ── exchange rate ──────────────────────────────────────────────────────────────

def apply_exchange_rates(rows: list[dict], company_currency: str) -> dict:
    """
    Attempt to fill ``exchange_rate`` and ``base_amount`` for every foreign-currency
    row that is still missing a rate.

    Calls ERP local records first, then online providers as fallback.
    Returns a summary:
        {fetched, already_set, failed, missing_pairs: [{from, to, date}, ...]}
    ``missing_pairs`` is de-duplicated — one entry per unique (from, to, date) that
    had no rate, so the UI can tell the user exactly which Currency Exchange records
    to create.
    """
    fetched = already_set = failed = 0
    missing_pairs: list[dict] = []
    seen_missing: set[tuple] = set()

    for row in rows:
        if row.get("validation_status") == "Error":
            continue
        src_cur = row.get("source_currency", "")
        if not src_cur or src_cur == company_currency:
            already_set += 1
            continue
        if row.get("txn_type") == "Transfer":
            continue
        if row.get("exchange_rate"):
            already_set += 1
            continue
        rate = _lookup_erp_rate(src_cur, company_currency, row["txn_date"])
        if rate:
            row["exchange_rate"] = rate
            row["base_amount"]   = round((row.get("raw_amount") or 0) * rate, 2)
            fetched += 1
        else:
            failed += 1
            key = (src_cur, company_currency, row["txn_date"])
            if key not in seen_missing:
                seen_missing.add(key)
                missing_pairs.append({"from": src_cur, "to": company_currency, "date": row["txn_date"]})

    return {
        "fetched": fetched,
        "already_set": already_set,
        "failed": failed,
        "missing_pairs": missing_pairs,
    }


def _resolve_exchange_rate(row: dict, company_currency: str) -> None:
    if row.get("validation_status") == "Error":
        return

    src_cur = row.get("source_currency", "")

    # Same-currency: already set to 1 by parser
    if src_cur == company_currency:
        return

    # Internal Transfer pairs: implied rate is computed at posting time.
    # External Transfer has only one leg in-file, so we should prefill from ERP.
    if row.get("txn_type") == "Transfer":
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
    Look up the exchange rate, in order:
      1. Currency Exchange table — direct DB query (no network, no error log noise).
      2. Inverse of any stored record for the opposite direction.
      3. Online providers (CDN-first so corporate proxies don't block them).
    Returns float or None.
    """
    # 1) Direct DB lookup — avoids ERPNext's get_exchange_rate which makes its own
    #    online calls (currently frankfurter.dev / 404 for PKR) and logs errors.
    rate = _query_currency_exchange_table(from_currency, to_currency, date)
    if rate:
        return rate

    # 2) Inverse direction stored in the table.
    inverse = _query_currency_exchange_table(to_currency, from_currency, date)
    if inverse and float(inverse) > 0:
        return round(1 / float(inverse), 10)

    # 3) Online fallback.
    return _lookup_online_rate(from_currency, to_currency, date)


def _query_currency_exchange_table(from_currency: str, to_currency: str, date: str):
    """
    Query the ``Currency Exchange`` DocType directly for the most recent rate
    on or before *date*.  Returns float or None — never makes a network call.
    """
    try:
        rows = frappe.db.get_all(
            "Currency Exchange",
            filters=[
                ["date",          "<=", date],
                ["from_currency", "=",  from_currency],
                ["to_currency",   "=",  to_currency],
            ],
            fields=["exchange_rate"],
            order_by="date desc",
            limit=1,
        )
        if rows and rows[0].get("exchange_rate"):
            rate = float(rows[0]["exchange_rate"])
            if rate > 0:
                return rate
    except Exception:
        pass
    return None


def _lookup_online_rate(from_currency: str, to_currency: str, date: str):
    """
    Try multiple public FX providers in order until one succeeds.
    Uses a 6-hour cache so repeated validate clicks don't hammer the network.
    Returns float or None.
    """
    if not (from_currency and to_currency and date):
        return None
    if from_currency == to_currency:
        return 1.0

    cache_key = f"cashew_online_fx:{date}:{from_currency}:{to_currency}"
    try:
        cached = frappe.cache().get_value(cache_key)
        if cached:
            return float(cached)
    except Exception:
        pass

    providers = [
        # CDN-served — extremely unlikely to be blocked by corporate proxies
        lambda: _fetch_fawaz_cdn_rate(from_currency, to_currency, date),
        lambda: _fetch_fawaz_api_rate(from_currency, to_currency, date),
        # Traditional REST providers
        lambda: _fetch_frankfurter_rate(from_currency, to_currency, date),
        lambda: _fetch_open_er_api_rate(from_currency, to_currency),
    ]

    for provider in providers:
        try:
            rate = provider()
            if rate and float(rate) > 0:
                rate = float(rate)
                try:
                    frappe.cache().set_value(cache_key, rate, expires_in_sec=21600)
                except Exception:
                    pass
                return rate
        except Exception:
            continue

    return None


def _fetch_fawaz_cdn_rate(from_currency: str, to_currency: str, date: str):
    """
    jsdelivr CDN mirror of fawazahmed0/currency-api.
    Static JSON files on CDN — passes most corporate proxies.
    Historical rates available back to 2021-01-01.
    """
    from_lower = from_currency.lower()
    to_lower   = to_currency.lower()
    url = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{date}/v1/currencies/{from_lower}.json"
    resp = requests.get(url, timeout=8)
    resp.raise_for_status()
    payload = resp.json() or {}
    rates = payload.get(from_lower) or {}
    return rates.get(to_lower)


def _fetch_fawaz_api_rate(from_currency: str, to_currency: str, date: str):
    """
    Direct API mirror of fawazahmed0/currency-api (fallback if CDN is slow).
    """
    from_lower = from_currency.lower()
    to_lower   = to_currency.lower()
    url = f"https://api.fawazahmed0.com/v1/currencies/{from_lower}"
    resp = requests.get(url, params={"date": date}, timeout=8)
    resp.raise_for_status()
    payload = resp.json() or {}
    rates = payload.get(from_lower) or {}
    return rates.get(to_lower)


def _fetch_frankfurter_rate(from_currency: str, to_currency: str, date: str):
    url = f"https://api.frankfurter.app/{date}"
    resp = requests.get(
        url,
        params={"from": from_currency, "to": to_currency},
        timeout=5,
    )
    resp.raise_for_status()
    payload = resp.json() or {}
    rates = payload.get("rates") or {}
    return rates.get(to_currency)


def _fetch_open_er_api_rate(from_currency: str, to_currency: str):
    url = f"https://open.er-api.com/v6/latest/{from_currency}"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    payload = resp.json() or {}
    rates = payload.get("rates") or {}
    return rates.get(to_currency)


# ── party resolution ───────────────────────────────────────────────────────────

def _resolve_party(row: dict, run) -> None:
    """
    Pre-fill ``resolved_party_type`` from ``txn_type`` — the only derivable
    invariant per f006 Decision 1 + existing requires_party semantics.

    The actual party master (``resolved_party``) is the user's job in the Vue
    Row Explorer (c006). Engine never writes ``resolved_party`` and never
    consults run-level default_customer / default_supplier.

    ``party_source`` is deprecated; engine writes nothing to it. Existing
    column preserved on the doctype for f004 revert backward compat.
    """
    if row.get("validation_status") == "Error":
        return

    txn_type = row.get("txn_type", "")
    if txn_type == "Loan Receivable":
        row["resolved_party_type"] = "Customer"
    elif txn_type == "Loan Payable":
        row["resolved_party_type"] = "Supplier"
    elif txn_type == "Income" and row.get("requires_party"):
        row["resolved_party_type"] = "Customer"
    elif txn_type == "Expense" and row.get("requires_party"):
        row["resolved_party_type"] = "Supplier"
    # else: leave resolved_party_type null — no party expected
