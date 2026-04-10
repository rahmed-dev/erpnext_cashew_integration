"""
C009-ext — Setup Wizard

Seeds Cashew Settings with default account and category mappings on install.
Can also be re-run manually or seeded from a custom Cashew CSV export.

Default data is derived from a real Cashew export and packaged with the app —
no CSV file or user input required at install time.

Entry points:
  run_setup(company=None)                — uses packaged defaults, auto-detects company
  run_setup_from_csv(company, csv_bytes) — parses a Cashew CSV and seeds from it
"""

import csv
import io

import frappe

_BALANCE_CORRECTION = "Balance Correction"

# ── packaged defaults (extracted from Cashew export 2026-04-08) ───────────────
#
# Each account: (cashew_account_name, currency)
# Each category: (category_name, subcategory, is_income)

_DEFAULT_ACCOUNTS: list[tuple[str, str]] = [
    ("Investment", "PKR"),
    ("NSave",      "USD"),
    ("Petty Cash", "PKR"),
    ("Saving",     "PKR"),
]

_DEFAULT_CATEGORIES: list[tuple[str, str, bool]] = [
    # ── income ────────────────────────────────────────────────────────────────
    ("Freelance",               "", True),
    ("Loan Payment Received",   "", True),
    ("Profit",                  "", True),
    ("Salary",                  "", True),
    ("Savings",                 "", True),
    # ── expense ───────────────────────────────────────────────────────────────
    ("Asset purchase",          "", False),
    ("Bank Charges",            "", False),
    ("Bike Maintenance",        "", False),
    ("Bills & Fees",            "", False),
    ("Claude",                  "", False),
    ("Codex",                   "", False),
    ("Cursor",                  "", False),
    ("Education",               "", False),
    ("Entertainment",           "", False),
    ("Family",                  "", False),
    ("Fruit",                   "", False),
    ("Fuel",                    "", False),
    ("Game Buy",                "", False),
    ("Govt. Fees",              "", False),
    ("Groceries",               "", False),
    ("Guest visit",             "", False),
    ("Haircut",                 "", False),
    ("Healthcare",              "", False),
    ("Home",                    "", False),
    ("Internet Expense",        "", False),
    ("Lent",                    "", False),
    ("Loss",                    "", False),
    ("Misc.",                   "", False),
    ("PC Build",                "", False),
    ("Party",                   "", False),
    ("Repair",                  "", False),
    ("Shopping",                "", False),
    ("Traffic Challan",         "", False),
    ("Unknown",                 "", False),
    ("Upwork Connect",          "", False),
]


# ── public entry points ────────────────────────────────────────────────────────

def run_setup(company: str | None = None) -> dict:
    """
    Seed Cashew Settings using packaged defaults.
    Auto-detects company from Global Defaults if not provided.
    Safe to call multiple times — already-mapped entries are skipped.
    """
    if not company:
        company = _get_default_company()
        if not company:
            return {"skipped": True, "reason": "No company found on site."}

    accounts   = {name: cur  for name, cur       in _DEFAULT_ACCOUNTS}
    categories = {(cat, sub): is_income
                  for cat, sub, is_income in _DEFAULT_CATEGORIES}

    return _do_setup(company, accounts, categories)


def run_setup_from_csv(company: str | None, csv_bytes: bytes) -> dict:
    """
    Seed Cashew Settings from a Cashew CSV export file.
    Parses unique accounts and categories from the file.
    Auto-detects company if not provided.
    """
    if not company:
        company = _get_default_company()
        if not company:
            frappe.throw("No company found on this site.", frappe.ValidationError)

    accounts, categories = _parse_csv(csv_bytes)
    return _do_setup(company, accounts, categories)


# ── core logic ─────────────────────────────────────────────────────────────────

def _do_setup(
    company: str,
    cashew_accounts: dict[str, str],
    categories: dict[tuple[str, str], bool],
) -> dict:
    income_parent  = _get_group_account(company, "Income")
    expense_parent = _get_group_account(company, "Expense")

    if not income_parent or not expense_parent:
        frappe.throw(
            f"Could not find Income and Expense root accounts for company '{company}'. "
            "Ensure the Chart of Accounts is set up before running this wizard.",
            frappe.ValidationError,
        )

    proposed_accounts: list[dict] = []
    for acct_name, currency in sorted(cashew_accounts.items()):
        erp_acct = _find_or_create_cash_account(acct_name, currency, company)
        proposed_accounts.append({
            "cashew_account_name": acct_name,
            "erp_account":         erp_acct,
        })

    proposed_categories: list[dict] = []
    for (cat, sub), is_income in sorted(categories.items()):
        parent   = income_parent if is_income else expense_parent
        erp_acct = _find_or_create_leaf_account(cat, parent, company)
        proposed_categories.append({
            "cashew_category":     cat,
            "cashew_sub_category": sub,
            "default_account":     erp_acct,
        })

    settings = frappe.get_single("Cashew Settings")
    if not settings.company:
        settings.company = company

    existing_accounts = {
        r.cashew_account_name
        for r in (settings.cashew_account_mapping or [])
    }
    existing_categories = {
        (r.cashew_category, r.cashew_sub_category or "")
        for r in (settings.cashew_category_mapping or [])
    }

    accounts_added = accounts_skipped = 0
    for row in proposed_accounts:
        if row["cashew_account_name"] in existing_accounts:
            accounts_skipped += 1
        else:
            settings.append("cashew_account_mapping", row)
            accounts_added += 1

    categories_added = categories_skipped = 0
    for row in proposed_categories:
        key = (row["cashew_category"], row["cashew_sub_category"])
        if key in existing_categories:
            categories_skipped += 1
        else:
            settings.append("cashew_category_mapping", row)
            categories_added += 1

    settings.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "accounts_added":     accounts_added,
        "accounts_skipped":   accounts_skipped,
        "categories_added":   categories_added,
        "categories_skipped": categories_skipped,
    }


# ── CSV parsing ────────────────────────────────────────────────────────────────

def _parse_csv(csv_bytes: bytes) -> tuple[dict, dict]:
    """Parse a Cashew CSV export into (accounts, categories) dicts."""
    text   = csv_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    categories: dict[tuple[str, str], bool] = {}
    accounts:   dict[str, str]              = {}

    for row in reader:
        acct     = (row.get("account")          or "").strip()
        currency = (row.get("currency")         or "").strip()
        category = (row.get("category name")    or "").strip()
        sub      = (row.get("subcategory name") or "").strip()
        income   = (row.get("income")           or "").strip().lower()

        if acct and currency:
            accounts[acct] = currency

        if not category or category == _BALANCE_CORRECTION:
            continue

        key = (category, sub)
        if key not in categories:
            categories[key] = income == "true"

    return accounts, categories


# ── helpers ────────────────────────────────────────────────────────────────────

def _get_default_company() -> str | None:
    company = frappe.db.get_single_value("Global Defaults", "default_company")
    if not company:
        company = frappe.db.get_value("Company", {}, "name", order_by="creation asc")
    return company


def _get_group_account(company: str, root_type: str) -> str | None:
    acct = frappe.db.get_value(
        "Account",
        {
            "company":        company,
            "root_type":      root_type,
            "is_group":       1,
            "parent_account": ["!=", ""],
        },
        "name",
        order_by="lft asc",
    )
    if acct:
        return acct
    return frappe.db.get_value(
        "Account",
        {"company": company, "root_type": root_type, "is_group": 1},
        "name",
        order_by="lft asc",
    )


def _find_or_create_leaf_account(
    account_name: str,
    parent_account: str,
    company: str,
) -> str:
    parent_root_type = frappe.db.get_value("Account", parent_account, "root_type")

    # Look for existing account on the correct side of the CoA.
    # Walk candidate names: base, base-1, base-2, ...
    # For each: if it exists on the correct side → return it.
    #           if it doesn't exist at all → create it.
    #           if it exists on the wrong side → try next suffix.
    candidate = account_name
    suffix = 0
    while True:
        existing = frappe.db.get_value(
            "Account",
            {"account_name": candidate, "company": company,
             "root_type": parent_root_type, "is_group": 0},
            "name",
        )
        if existing:
            return existing

        clash = frappe.db.get_value(
            "Account",
            {"account_name": candidate, "company": company, "is_group": 0},
            "name",
        )
        if not clash:
            break  # name is free — create it

        suffix += 1
        candidate = f"{account_name}-{suffix}"

    doc = frappe.get_doc({
        "doctype":        "Account",
        "account_name":   candidate,
        "parent_account": parent_account,
        "company":        company,
        "is_group":       0,
    })
    doc.insert(ignore_permissions=True)
    return doc.name


def _find_or_create_cash_account(account_name: str, currency: str, company: str) -> str:
    existing = frappe.db.get_value(
        "Account",
        {"account_name": account_name, "company": company, "is_group": 0,
         "account_type": ["in", ["Cash", "Bank"]]},
        "name",
    )
    if existing:
        return existing

    existing = frappe.db.get_value(
        "Account",
        {"account_name": account_name, "company": company, "is_group": 0},
        "name",
    )
    if existing:
        return existing

    parent = (
        frappe.db.get_value(
            "Account",
            {"company": company, "account_type": "Cash", "is_group": 1},
            "name",
            order_by="lft asc",
        )
        or frappe.db.get_value(
            "Account",
            {"company": company, "root_type": "Asset", "is_group": 1, "parent_account": ["!=", ""]},
            "name",
            order_by="lft asc",
        )
    )

    if not parent:
        frappe.throw(
            f"Cannot find a suitable parent for Cash account '{account_name}' "
            f"in company '{company}'. Create a Cash group account first.",
            frappe.ValidationError,
        )

    doc = frappe.get_doc({
        "doctype":          "Account",
        "account_name":     account_name,
        "parent_account":   parent,
        "account_type":     "Cash",
        "account_currency": currency,
        "company":          company,
        "is_group":         0,
    })
    doc.insert(ignore_permissions=True)
    return doc.name
