"""
Shared Cashew Category Mapping lookup.

Single source of truth used by parser (initial txn_type assignment), mapping
engine (account/party resolution), and validation (option-b re-evaluation
after category_type edits).
"""

import frappe


def build_category_type_map() -> dict[tuple[str, str], dict]:
    """Return active Cashew Category Mapping rows keyed by
    ``(cashew_category, cashew_sub_category)``.

    Each value carries the fields downstream code needs:
        - ``category_type`` (Income | Expense | Loan Out | Loan In)
        - ``default_account``
        - ``requires_party``
        - ``is_active``

    Inactive mappings are filtered out — unmapped rows then fall through to
    parser's direction-based fallback and validate-time error handling, which
    matches the pre-f006 mapping engine behavior.

    Single ``frappe.get_all`` against the child table — no recursive doc loads.
    """
    result: dict[tuple[str, str], dict] = {}
    rows = frappe.get_all(
        "Cashew Category Mapping",
        filters={"is_active": 1},
        fields=[
            "cashew_category",
            "cashew_sub_category",
            "category_type",
            "default_account",
            "requires_party",
            "is_active",
        ],
    )
    for r in rows:
        key = (r["cashew_category"], r["cashew_sub_category"] or "")
        result[key] = {
            "category_type":  r["category_type"],
            "default_account": r["default_account"],
            "requires_party":  bool(r["requires_party"]),
            "is_active":       bool(r["is_active"]),
        }
    return result
