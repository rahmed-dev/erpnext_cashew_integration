"""
f012 c012 — Cashew Budget import.

Budgets live entirely outside the row pipeline. ``sqlite_reader.read_budgets``
reads them from the backup; this module resolves their scope through the mapping
tables and upserts a ``Cashew Budget`` per ``budget_pk``. Nothing here touches a
run counter, marks a row, or posts a document, and a revert leaves budgets alone
— they are reference data, not postings.

Two rules this module exists to enforce.

**The mapping gate (f012 Decision 6).** A budget whose scope is not FULLY mapped
is not imported. Budget actuals are computed from GL Entry against the resolved
accounts, so an unmapped scope member is a hole in the figure — and it fails in
the dangerous direction: a limit missing one of its categories reads UNDER limit
when it has in fact been blown. Unresolved members are reported so the import
surface can offer them for mapping (f012 c014), and re-importing then picks the
budget up. Never a dead end.

**Scope is materialised, not referenced.** An empty ``category_fks`` means ALL
categories in Cashew, and an empty ``wallet_fks`` means ALL wallets. Both are
expanded at import time into the actual mapped accounts, because the consumer
(``dashboard_series.budget_cycles``) measures spend against a concrete account
list. The consequence is that a category mapped AFTER a budget was imported is
not retroactively in scope until the next budget import — which is exactly what
the budgets-only sync (c015) is for.
"""

import frappe

from cashew_integration.importer.category_lookup import build_category_type_map

BUDGET_DOCTYPE = "Cashew Budget"


# ── scope resolution ───────────────────────────────────────────────────────────

def _account_name_map() -> dict[str, str]:
    """Active Cashew account name → ERP account, from the Cashew Settings child table."""
    settings = frappe.get_single("Cashew Settings")
    return {
        (row.cashew_account_name or "").strip(): row.erp_account
        for row in (settings.cashew_account_mapping or [])
        if row.is_active and row.cashew_account_name and row.erp_account
    }


def _resolve_category(member: dict, category_map: dict) -> dict | None:
    """Resolve one category scope member to its mapping, or ``None`` if unmapped.

    Mirrors the engine's fallback exactly: an explicit ``(category, sub)`` mapping
    wins, and a category-only mapping covers every sub-category under it. Any
    other order would report a sub-category as unmapped that the import itself
    resolves happily.
    """
    category = (member.get("category") or "").strip()
    if not category:
        return None  # PK did not resolve to a name at all (master deleted in Cashew)
    sub = (member.get("sub_category") or "").strip()
    mapping = category_map.get((category, sub)) or category_map.get((category, ""))
    if not mapping or not mapping.get("default_account"):
        return None
    return {
        "cashew_category": category,
        "cashew_sub_category": sub,
        "account": mapping["default_account"],
        "category_pk": member.get("pk"),
    }


def resolve_scope(budget: dict, category_map: dict, account_map: dict) -> dict:
    """Resolve a budget's category / exclude / wallet scope into ERP accounts.

    Returns ``{"accounts", "excluded", "wallets", "unresolved"}``. ``unresolved``
    being non-empty is the gate: the caller must not import the budget.
    """
    unresolved: list[dict] = []

    # ── excludes first: they narrow the scope, and an exclude that does not
    # resolve is NOT a hole. Excluding something that is unmapped removes nothing
    # from a figure built only from mapped accounts, so it must not gate the
    # import — treating it as a blocker would refuse a budget for a member that
    # cannot affect its number.
    excluded: list[dict] = []
    excluded_keys: set[tuple[str, str]] = set()
    excluded_pks: set[str] = set()
    for member in budget.get("category_exclude") or []:
        excluded_pks.add(str(member.get("pk")))
        resolved = _resolve_category(member, category_map)
        if resolved:
            excluded.append(resolved)
            excluded_keys.add((resolved["cashew_category"], resolved["cashew_sub_category"]))
        else:
            excluded.append({
                "cashew_category": member.get("category") or "",
                "cashew_sub_category": member.get("sub_category") or "",
                "account": None,
                "category_pk": member.get("pk"),
            })

    # ── category scope
    accounts: list[dict] = []
    scope = budget.get("category_scope") or []
    if scope:
        for member in scope:
            if str(member.get("pk")) in excluded_pks:
                continue
            resolved = _resolve_category(member, category_map)
            if resolved is None:
                unresolved.append({
                    "kind": "category",
                    "pk": member.get("pk"),
                    "category": member.get("category") or "",
                    "sub_category": member.get("sub_category") or "",
                })
                continue
            if (resolved["cashew_category"], resolved["cashew_sub_category"]) in excluded_keys:
                continue
            accounts.append(resolved)
    else:
        # No category restriction — every mapped category is in scope.
        for (category, sub), mapping in category_map.items():
            if not mapping.get("default_account"):
                continue
            if (category, sub) in excluded_keys or (category, "") in excluded_keys:
                continue
            accounts.append({
                "cashew_category": category,
                "cashew_sub_category": sub,
                "account": mapping["default_account"],
                "category_pk": None,
            })

    # ── wallet scope. Empty means ALL wallets; the scalar `wallet_fk` column is a
    # display anchor and is deliberately not read (f012 C5.1).
    wallets: list[dict] = []
    wallet_scope = budget.get("wallet_scope") or []
    if wallet_scope:
        for member in wallet_scope:
            name = (member.get("wallet") or "").strip()
            account = account_map.get(name) if name else None
            if not account:
                unresolved.append({
                    "kind": "account",
                    "pk": member.get("pk"),
                    "account_name": name,
                })
                continue
            wallets.append({
                "cashew_account_name": name,
                "account": account,
                "wallet_pk": member.get("pk"),
            })
    else:
        wallets = [
            {"cashew_account_name": name, "account": account, "wallet_pk": None}
            for name, account in sorted(account_map.items())
        ]

    return {
        "accounts": _dedupe(accounts, ("cashew_category", "cashew_sub_category")),
        "excluded": excluded,
        "wallets": _dedupe(wallets, ("cashew_account_name",)),
        "unresolved": unresolved,
    }


def _dedupe(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    seen = set()
    out = []
    for row in rows:
        key = tuple(row.get(k) for k in keys)
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


# ── upsert ─────────────────────────────────────────────────────────────────────

def import_budgets(budgets: list[dict], company: str, run_name: str | None = None) -> dict:
    """Upsert every fully-mapped budget; report the rest. Returns a summary dict.

    ``{"imported": [pks], "created": [...], "updated": [...], "unchanged": [...],
       "skipped": [{"budget_name", "budget_pk", "unresolved"}]}``

    The three outcome lists exist for the budgets-only sync (c015), which is
    re-run by hand and has to be able to say what it actually changed. A sync
    that reports "2 budgets imported" every time teaches the operator nothing
    about whether their Cashew edit landed.

    Permissions are deliberately bypassed on the write: the operator's right to
    run the import is the authorisation, and budgets are a by-product of it — an
    Accountant who can post a whole ledger should not have a run half-succeed
    because they hold read-only rights on a reference doctype.
    """
    if not budgets:
        return {"imported": [], "created": [], "updated": [], "unchanged": [], "skipped": []}

    category_map = build_category_type_map()
    account_map = _account_name_map()

    imported: list[str] = []
    by_outcome: dict[str, list[str]] = {"created": [], "updated": [], "unchanged": []}
    skipped: list[dict] = []

    for budget in budgets:
        if not budget.get("start_date"):
            # Without an anchor there is no cycle grid, so there is nothing to chart.
            skipped.append({
                "budget_name": budget.get("budget_name"),
                "budget_pk": budget.get("budget_pk"),
                "unresolved": [{"kind": "start_date"}],
            })
            continue

        scope = resolve_scope(budget, category_map, account_map)
        if scope["unresolved"] or not scope["accounts"]:
            skipped.append({
                "budget_name": budget.get("budget_name"),
                "budget_pk": budget.get("budget_pk"),
                "unresolved": scope["unresolved"] or [{"kind": "empty_scope"}],
            })
            continue

        outcome = _upsert(budget, scope, company, run_name)
        by_outcome[outcome].append(budget.get("budget_pk"))
        imported.append(budget.get("budget_pk"))

    return {"imported": imported, "skipped": skipped, **by_outcome}


# Fields compared to decide created / updated / unchanged. `source_run` is
# deliberately absent: re-running the sync from a second backup would otherwise
# report every budget as changed when nothing about the budget itself moved.
_TRACKED_FIELDS = (
    "company", "budget_name", "amount", "is_income", "start_date",
    "reoccurrence", "period_length", "is_archived", "is_pinned", "disabled",
)
_TRACKED_TABLES = {
    "budget_accounts": ("cashew_category", "cashew_sub_category", "account"),
    "excluded_categories": ("cashew_category", "cashew_sub_category", "account"),
    "budget_wallets": ("cashew_account_name", "account"),
}


def _snapshot(doc) -> tuple:
    """A comparable view of everything the import writes."""
    scalars = tuple(str(doc.get(f) or "") for f in _TRACKED_FIELDS)
    tables = tuple(
        tuple(sorted(
            tuple(str(row.get(f) or "") for f in fields)
            for row in (doc.get(table) or [])
        ))
        for table, fields in _TRACKED_TABLES.items()
    )
    return (scalars, tables)


def _upsert(budget: dict, scope: dict, company: str, run_name: str | None) -> str:
    """Write the budget. Returns ``created``, ``updated`` or ``unchanged``."""
    pk = budget["budget_pk"]
    existed = bool(frappe.db.exists(BUDGET_DOCTYPE, pk))
    if existed:
        doc = frappe.get_doc(BUDGET_DOCTYPE, pk)
        before = _snapshot(doc)
    else:
        doc = frappe.new_doc(BUDGET_DOCTYPE)
        doc.budget_pk = pk
        before = None

    doc.company = company
    doc.budget_name = budget.get("budget_name") or pk
    doc.amount = budget.get("amount") or 0.0
    doc.is_income = budget.get("is_income") or 0
    doc.start_date = budget["start_date"]
    doc.reoccurrence = budget["reoccurrence"]
    doc.period_length = budget.get("period_length") or 1
    doc.is_archived = budget.get("is_archived") or 0
    doc.is_pinned = budget.get("is_pinned") or 0
    # Cashew's `archived` flag is the real inactive signal. `end_date` ends the
    # FIRST period only — deriving activity from it marks every budget expired.
    doc.disabled = doc.is_archived
    if run_name:
        doc.source_run = run_name

    # Scope is rewritten wholesale rather than merged: a category removed from the
    # budget in Cashew must disappear here too, and a merge would keep it forever.
    doc.set("budget_accounts", scope["accounts"])
    doc.set("excluded_categories", scope["excluded"])
    doc.set("budget_wallets", scope["wallets"])

    if before is not None and _snapshot(doc) == before:
        # Nothing the import owns has moved. Skipping the save keeps `modified`
        # and the version trail honest — a re-run that changed nothing must not
        # look, in the document history, like an edit.
        return "unchanged"

    doc.save(ignore_permissions=True)
    return "created" if not existed else "updated"
