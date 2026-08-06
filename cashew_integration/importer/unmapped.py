"""
f012 c014 — inline unmapped-entity resolution.

An import stalls when the file references a Cashew account or category that has
no active mapping row. Until now the only cure was leaving the import, opening
Cashew Settings on Desk, adding the row, coming back and re-validating. This
module is the engine behind doing it without leaving the import surface.

Two halves:

``collect_unmapped(run)``
    Reports every Cashew account and (category, sub-category) pair the run's
    rows reference that no active mapping resolves, with the row count and a
    suggested account currency / category type so the user is filling in a
    proposal rather than an empty form. Read-only.

``apply_resolutions(...)``
    Writes the chosen mappings as real ``Cashew Account Mapping`` /
    ``Cashew Category Mapping`` child rows on Cashew Settings.

Two things worth knowing before changing this:

1. **The mapping tables are keyed on the Cashew NAME, not on a Cashew primary
   key.** ``Cashew Account Mapping.cashew_account_name`` and
   ``Cashew Category Mapping.cashew_category`` are Data fields holding the
   name as it appears in the export. The CSV export carries no PKs at all, so
   the name is the only key available on this path. A future budget-scope
   consumer (f012 c012) holds opaque PK strings and must resolve them to names
   through the SQLite ``categories`` / ``wallets`` tables before asking this
   module about them — it must not pass a PK in as a name.

2. **Validation is not re-implemented here.** ``Cashew Category Mapping``
   enforces the account-class predicate (Income category needs an Income
   account, Loan Out needs an Asset/Receivable, and so on) in its own
   controller ``validate``, which Frappe runs when the parent Settings doc is
   saved. ``apply_resolutions`` deliberately lets that ``frappe.throw``
   propagate to the caller instead of catching it, so the user sees the real
   reason the account was rejected.
"""

import frappe

from cashew_integration.importer.category_lookup import build_category_type_map
from cashew_integration.importer.mapping import _extract_partner_name

# Rows of these types never go through a category lookup (parser sets the route
# directly), so a missing category mapping is not a blocker for them.
_CATEGORY_EXEMPT_TXN_TYPES = {"Transfer", "External Transfer", "Adjustment"}

# The account class each category_type demands, mirrored from
# validation._CATEGORY_TYPE_EXPECTATIONS. Used ONLY to narrow the account
# picker in the UI — the controller validate above is the actual gate.
CATEGORY_TYPE_ROOT_TYPES = {
    "Income": "Income",
    "Expense": "Expense",
    "Loan Out": "Asset",
    "Loan In": "Liability",
}

# Sample row labels carried back per entity, so the user can see what kind of
# transaction they are about to route without opening the workbench.
_SAMPLES_PER_ENTITY = 3


def collect_unmapped(run) -> dict:
    """Return the unmapped accounts and categories referenced by *run*'s rows.

    Shape::

        {
          "accounts": [{cashew_account_name, row_count, suggested_currency,
                        currency_ambiguous, samples: [...]}],
          "categories": [{cashew_category, cashew_sub_category, row_count,
                          suggested_category_type, samples: [...]}],
        }

    Both lists are sorted by row_count descending — the entity blocking the
    most rows is the one worth fixing first.
    """
    rows = frappe.get_all(
        "Cashew Import Row",
        filters={"parent": run.name, "parenttype": "Cashew Import Run"},
        fields=[
            "row_idx", "raw_account", "category", "sub_category", "txn_type",
            "source_currency", "income_flag", "title", "note",
        ],
        order_by="row_idx asc",
    )

    settings = frappe.get_single("Cashew Settings")
    mapped_accounts = {
        r.cashew_account_name for r in (settings.cashew_account_mapping or []) if r.is_active
    }
    category_map = build_category_type_map()

    accounts: dict[str, dict] = {}
    categories: dict[tuple[str, str], dict] = {}

    for row in rows:
        _collect_account(row, mapped_accounts, accounts)
        _collect_category(row, category_map, categories)

    return {
        "accounts": sorted(
            (_finish_account(a) for a in accounts.values()),
            key=lambda a: (-a["row_count"], a["cashew_account_name"]),
        ),
        "categories": sorted(
            (_finish_category(c) for c in categories.values()),
            key=lambda c: (-c["row_count"], c["cashew_category"], c["cashew_sub_category"]),
        ),
    }


def _collect_account(row, mapped_accounts: set, accounts: dict) -> None:
    """Record the row's own account, and — for external transfers — its partner.

    The partner account only exists inside the transfer note, so it is invisible
    to a plain scan of raw_account, yet an unmapped partner blocks the row just
    as hard (EXTERNAL_ACCOUNT_NOT_MAPPED).
    """
    for name in (row.raw_account, _partner_account(row)):
        if not name or name in mapped_accounts:
            continue
        entry = accounts.setdefault(name, {
            "cashew_account_name": name,
            "row_count": 0,
            "currencies": {},
            "samples": [],
        })
        entry["row_count"] += 1
        currency = row.source_currency or ""
        if currency:
            entry["currencies"][currency] = entry["currencies"].get(currency, 0) + 1
        _add_sample(entry, row)


def _partner_account(row) -> str:
    if row.txn_type != "External Transfer":
        return ""
    # _extract_partner_name reads a dict, and needs both keys it parses on.
    return _extract_partner_name({"raw_account": row.raw_account, "note": row.note or ""})


def _collect_category(row, category_map: dict, categories: dict) -> None:
    if row.txn_type in _CATEGORY_EXEMPT_TXN_TYPES:
        return
    category = row.category or ""
    if not category:
        return
    sub = row.sub_category or ""
    # Same fallback order the mapping engine uses: exact pair, then category-only.
    if category_map.get((category, sub)) or category_map.get((category, "")):
        return
    entry = categories.setdefault((category, sub), {
        "cashew_category": category,
        "cashew_sub_category": sub,
        "row_count": 0,
        "income_rows": 0,
        "samples": [],
    })
    entry["row_count"] += 1
    if row.income_flag:
        entry["income_rows"] += 1
    _add_sample(entry, row)


def _add_sample(entry: dict, row) -> None:
    if len(entry["samples"]) >= _SAMPLES_PER_ENTITY:
        return
    entry["samples"].append({
        "row_idx": row.row_idx,
        "title": row.title or "",
    })


def _finish_account(entry: dict) -> dict:
    """Pick the currency to propose, and say so if the rows disagree."""
    currencies = entry.pop("currencies")
    ranked = sorted(currencies.items(), key=lambda kv: (-kv[1], kv[0]))
    entry["suggested_currency"] = ranked[0][0] if ranked else None
    entry["currency_ambiguous"] = len(ranked) > 1
    return entry


def _finish_category(entry: dict) -> dict:
    """Propose Income or Expense from the direction the rows actually carry.

    Loan Out / Loan In are never proposed — a loan is a routing decision the
    export cannot express, and guessing it would silently post to the wrong
    side of the balance sheet.
    """
    income_rows = entry.pop("income_rows")
    entry["suggested_category_type"] = "Income" if income_rows > entry["row_count"] / 2 else "Expense"
    return entry


def apply_resolutions(accounts: list[dict], categories: list[dict]) -> dict:
    """Write the given mappings onto Cashew Settings and return what changed.

    An entry whose key already exists is UPDATED in place (and reactivated)
    rather than appended — the Settings controller rejects duplicate account
    names and duplicate (category, sub-category) pairs, so appending a second
    row for a key the user had previously deactivated would fail the save and
    strand the whole batch.

    Raises whatever the Settings / child validators raise. Callers must not
    swallow it: an account-class mismatch is the single most useful thing this
    surface can tell the user.
    """
    settings = frappe.get_single("Cashew Settings")

    account_rows = {r.cashew_account_name: r for r in (settings.cashew_account_mapping or [])}
    category_rows = {
        (r.cashew_category, r.cashew_sub_category or ""): r
        for r in (settings.cashew_category_mapping or [])
    }

    written = {"accounts": 0, "categories": 0}

    for item in accounts or []:
        name = (item.get("cashew_account_name") or "").strip()
        erp_account = (item.get("erp_account") or "").strip()
        currency = (item.get("account_currency") or "").strip()
        if not (name and erp_account and currency):
            frappe.throw(
                f"Account mapping for '{name or '(unnamed)'}' needs both an ERP "
                "account and an account currency.",
                frappe.ValidationError,
            )
        existing = account_rows.get(name)
        if existing:
            existing.erp_account = erp_account
            existing.account_currency = currency
            existing.is_active = 1
        else:
            settings.append("cashew_account_mapping", {
                "cashew_account_name": name,
                "erp_account": erp_account,
                "account_currency": currency,
                "is_active": 1,
            })
        written["accounts"] += 1

    for item in categories or []:
        category = (item.get("cashew_category") or "").strip()
        sub = (item.get("cashew_sub_category") or "").strip()
        category_type = (item.get("category_type") or "").strip()
        default_account = (item.get("default_account") or "").strip()
        if not (category and category_type and default_account):
            frappe.throw(
                f"Category mapping for '{category or '(unnamed)'}' needs both a "
                "category type and a default account.",
                frappe.ValidationError,
            )
        requires_party = 1 if item.get("requires_party") else 0
        existing = category_rows.get((category, sub))
        if existing:
            existing.category_type = category_type
            existing.default_account = default_account
            existing.requires_party = requires_party
            existing.is_active = 1
        else:
            settings.append("cashew_category_mapping", {
                "cashew_category": category,
                "cashew_sub_category": sub,
                "category_type": category_type,
                "default_account": default_account,
                "requires_party": requires_party,
                "is_active": 1,
            })
        written["categories"] += 1

    settings.save()
    return written
