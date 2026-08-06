"""
Opening balances for cash and bank accounts.

Cashew exports transactions, never balances. Importing a mid-life history into a
fresh ERPNext chart therefore starts every account at zero, and the ledger
records only the movements since the first imported day. Accounts that were
already holding money come out understated by exactly the amount they held on
the day before the import window — which is how a physical cash account ends up
with a negative balance.

The app cannot know the true opening figure; only the person who counted the
cash can. What it *can* do is prove an opening balance is missing and state the
smallest one that is arithmetically possible:

    suggested_minimum = -(lowest running balance over the whole ledger)

Any account whose running balance ever goes below zero is missing at least that
much. The real figure is usually larger.
"""

import frappe
from frappe.utils import add_days, flt


DEFAULT_OPENING_ACCOUNT_NAMES = ("Temporary Opening", "Opening Balance")


# ── detection ──────────────────────────────────────────────────────────────────

def audit_opening_balances(company: str) -> list[dict]:
    """
    Walk every leaf Cash/Bank account and report whether it is missing an opening
    balance, with the smallest opening that would keep it non-negative throughout.

    Read-only.
    """
    accounts = frappe.get_all(
        "Account",
        filters={
            "company": company,
            "is_group": 0,
            "account_type": ["in", ["Cash", "Bank"]],
        },
        fields=["name", "account_name", "account_currency"],
        order_by="name asc",
    )

    company_currency = frappe.get_cached_value("Company", company, "default_currency")
    results = []

    for account in accounts:
        entries = frappe.get_all(
            "GL Entry",
            filters={"account": account.name, "is_cancelled": 0},
            fields=["posting_date", "debit", "credit", "creation"],
            order_by="posting_date asc, creation asc",
        )
        if not entries:
            continue

        balance = 0.0
        lowest = 0.0
        lowest_on = None
        for entry in entries:
            balance += flt(entry.debit) - flt(entry.credit)
            if balance < lowest:
                lowest = balance
                lowest_on = entry.posting_date

        results.append({
            "account": account.name,
            "account_currency": account.account_currency,
            "company_currency": company_currency,
            "first_entry_on": entries[0].posting_date,
            "closing_balance": round(balance, 2),
            "lowest_running_balance": round(lowest, 2),
            "lowest_on": lowest_on,
            # Lower bound, in company currency. The true opening is >= this.
            "suggested_minimum_opening": round(-lowest, 2) if lowest < 0 else 0.0,
            "missing_opening_balance": lowest < 0,
        })

    return results


def suggested_opening_date(company: str) -> str | None:
    """The day before the earliest Cashew-imported transaction for *company*."""
    earliest = frappe.db.get_value(
        "Cashew Import Run",
        {"company": company, "period_start": ["is", "set"]},
        "min(period_start)",
    )
    return add_days(earliest, -1) if earliest else None


# ── posting ────────────────────────────────────────────────────────────────────

def post_opening_entry(
    company: str,
    posting_date: str,
    balances: list[dict],
    opening_account: str | None = None,
    submit: bool = True,
) -> str:
    """
    Create one ERPNext Opening Entry crediting *opening_account* and debiting each
    account in *balances*.

    ``balances`` items: ``{"account": str, "amount": float, "exchange_rate": float}``
    where ``amount`` is in the account's own currency (``exchange_rate`` is only
    needed for foreign-currency accounts and defaults to 1).

    Returns the Journal Entry name. Raises if the company already has an opening
    entry on that date — this is meant to run exactly once.
    """
    if not balances:
        frappe.throw("No opening balances supplied.")

    opening_account = opening_account or _find_opening_account(company)
    company_currency = frappe.get_cached_value("Company", company, "default_currency")

    existing = frappe.db.exists(
        "Journal Entry",
        {
            "company": company,
            "voucher_type": "Opening Entry",
            "posting_date": posting_date,
            "docstatus": ["<", 2],
        },
    )
    if existing:
        frappe.throw(
            f"Opening Entry {existing} already exists for {company} on {posting_date}. "
            "Amend or cancel it rather than posting a second one."
        )

    accounts = []
    total_base = 0.0

    for item in balances:
        account = item["account"]
        amount = flt(item["amount"])
        if not amount:
            continue
        rate = flt(item.get("exchange_rate") or 1)
        currency = frappe.get_cached_value("Account", account, "account_currency") \
            or company_currency
        if currency != company_currency and rate == 1:
            frappe.throw(
                f"{account} is denominated in {currency} but no exchange_rate was "
                f"supplied. Posting it at 1.0 would book {currency} into a "
                f"{company_currency} column."
            )
        base = round(amount * rate, 2)
        total_base += base
        accounts.append({
            "account": account,
            "debit_in_account_currency": amount,
            "credit_in_account_currency": 0,
            "exchange_rate": rate,
            "account_currency": currency,
            "debit": base,
        })

    if not accounts:
        frappe.throw("Every supplied opening balance was zero.")

    accounts.append({
        "account": opening_account,
        "debit_in_account_currency": 0,
        "credit_in_account_currency": round(total_base, 2),
        "exchange_rate": 1.0,
        "account_currency": company_currency,
        "credit": round(total_base, 2),
    })

    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Opening Entry",
        "is_opening": "Yes",
        "company": company,
        "posting_date": posting_date,
        "multi_currency": 1 if any(a["account_currency"] != company_currency
                                   for a in accounts) else 0,
        "remark": (
            "Cashew: opening balances carried into ERPNext for the day before the "
            "first imported transaction."
        ),
        "accounts": accounts,
    })
    je.insert()
    if submit:
        je.submit()
    return je.name


def _find_opening_account(company: str) -> str:
    for account_name in DEFAULT_OPENING_ACCOUNT_NAMES:
        found = frappe.db.get_value(
            "Account",
            {"company": company, "account_name": account_name, "is_group": 0},
            "name",
        )
        if found:
            return found
    frappe.throw(
        f"No opening account found for {company}. Expected one of "
        f"{', '.join(DEFAULT_OPENING_ACCOUNT_NAMES)}; pass opening_account explicitly."
    )
