"""
Unit tests for C003 — Mapping + Preview Override Engine.

Uses real ERP accounts from Code.Solutions (work.local) and real category
names from cashew-2026-04-08-21-22-58-504687.csv.

Tests call internal helpers directly to avoid Frappe DB lookups where possible,
and call apply_mappings() with a mocked Cashew Settings doc for full-path tests.

Run:  bench --site work.local run-tests --module cashew_integration.tests.test_mapping
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from cashew_integration.importer.mapping import (
    _build_account_map,
    _build_category_map,
    _resolve_category,
    _resolve_erp_account,
    _resolve_party,
    apply_mappings,
)

# ── real account pairings (Cashew → Code.Solutions ERP) ───────────────────────
ACCOUNT_PAIRS = [
    ("Petty Cash",  "Cash - CS",          "PKR"),
    ("NSave",       "Meezan Bank - CS",    "PKR"),
    ("Saving",      "Crypto - CS",         "PKR"),
    ("Investment",  "Earnest Money - CS",  "PKR"),
]

# ── category mappings derived from the real CSV ────────────────────────────────
# (cashew_category, cashew_sub_category, default_route, default_account)
CATEGORY_PAIRS = [
    ("Freelance",        "",  "Sales Invoice",   "Service - CS"),
    ("Salary",           "",  "Sales Invoice",   "Service - CS"),
    ("Entertainment",    "",  "Journal Entry",   "Entertainment Expenses - CS"),
    ("Home",             "",  "Journal Entry",   "Office Maintenance Expenses - CS"),
    ("Family",           "",  "Journal Entry",   "Administrative Expenses - CS"),
    ("Internet Expense", "",  "Journal Entry",   "Utility Expenses - CS"),
    ("Bills & Fees",     "",  "Journal Entry",   "Miscellaneous Expenses - CS"),
    ("Cursor",           "",  "Journal Entry",   "Miscellaneous Expenses - CS"),
    ("Bank Charges",     "",  "Journal Entry",   "Write Off - CS"),
    ("Fuel",             "",  "Journal Entry",   "Travel Expenses - CS"),
    ("Groceries",        "",  "Journal Entry",   "Administrative Expenses - CS"),
    ("Healthcare",       "",  "Journal Entry",   "Miscellaneous Expenses - CS"),
    ("Education",        "",  "Journal Entry",   "Miscellaneous Expenses - CS"),
    ("Shopping",         "",  "Journal Entry",   "Sales Expenses - CS"),
    ("PC Build",         "",  "Journal Entry",   "Electronic Equipments - CS"),
]


def _make_settings():
    """Return a mock Cashew Settings doc matching our real account/category tables."""
    acct_rows = [
        MagicMock(
            cashew_account_name=ca,
            erp_account=ea,
            account_currency=cur,
            is_active=True,
        )
        for ca, ea, cur in ACCOUNT_PAIRS
    ]
    cat_rows = [
        MagicMock(
            cashew_category=cat,
            cashew_sub_category=sub,
            default_route=route,
            default_account=acct,
            is_active=True,
        )
        for cat, sub, route, acct in CATEGORY_PAIRS
    ]
    s = MagicMock()
    s.cashew_account_mapping = acct_rows
    s.cashew_category_mapping = cat_rows
    return s


def _make_run(company="Code.Solutions", default_customer=None,
              default_supplier=None, expense_threshold=0):
    r = SimpleNamespace(
        company=company,
        company_currency="PKR",
        default_customer=default_customer,
        default_supplier=default_supplier,
        expense_threshold=expense_threshold,
    )
    return r


def _base_row(account="Petty Cash", currency="PKR", category="Entertainment",
              sub_category="", txn_type="Expense", amount=2240.0, date="2026-04-08"):
    return {
        "row_idx": 1,
        "validation_status": "Valid",
        "validation_error_code": None,
        "validation_error_message": None,
        "raw_account": account,
        "source_currency": currency,
        "company_currency": "PKR",
        "category": category,
        "sub_category": sub_category,
        "txn_type": txn_type,
        "raw_amount": amount,
        "txn_date": date,
        "income_flag": "false",
        "exchange_rate": 1.0 if currency == "PKR" else None,
        "base_amount": amount if currency == "PKR" else 0.0,
    }


class TestAccountMapping(FrappeTestCase):
    """_resolve_erp_account populates resolved_erp_account or blocks the row."""

    def setUp(self):
        self.acct_map = _build_account_map(_make_settings())

    def test_mapped_account_resolves_correctly(self):
        for cashew_name, erp_name, _ in ACCOUNT_PAIRS:
            row = _base_row(account=cashew_name)
            _resolve_erp_account(row, self.acct_map)
            self.assertEqual(row["resolved_erp_account"], erp_name,
                             f"'{cashew_name}' should resolve to '{erp_name}'")
            self.assertEqual(row["validation_status"], "Valid")

    def test_unmapped_account_sets_error(self):
        row = _base_row(account="Unknown Account")
        _resolve_erp_account(row, self.acct_map)
        self.assertEqual(row["validation_status"], "Error")
        self.assertEqual(row["validation_error_code"], "CASHEW_ACCOUNT_NOT_MAPPED")

    def test_all_four_cashew_accounts_are_mapped(self):
        for cashew_name, _, _ in ACCOUNT_PAIRS:
            self.assertIn(cashew_name, self.acct_map,
                          f"'{cashew_name}' must appear in account map.")


class TestCategoryMapping(FrappeTestCase):
    """_resolve_category sets resolved_route and resolved_account for non-transfer rows."""

    def setUp(self):
        self.cat_map = _build_category_map(_make_settings())

    def test_expense_category_resolves_to_journal_entry(self):
        for cat, _, route, acct in CATEGORY_PAIRS:
            if route == "Journal Entry":
                row = _base_row(category=cat, txn_type="Expense")
                _resolve_category(row, self.cat_map)
                self.assertEqual(row.get("resolved_route"), route,
                                 f"Category '{cat}' → route mismatch")
                self.assertEqual(row.get("resolved_account"), acct,
                                 f"Category '{cat}' → account mismatch")

    def test_income_category_resolves_to_sales_invoice(self):
        row = _base_row(category="Freelance", txn_type="Income")
        _resolve_category(row, self.cat_map)
        self.assertEqual(row["resolved_route"], "Sales Invoice")
        self.assertEqual(row["resolved_account"], "Service - CS")

    def test_sub_category_fallback_to_empty_sub(self):
        """(category, unknown_sub) falls back to (category, '') mapping."""
        row = _base_row(category="Entertainment", sub_category="Cinema")
        _resolve_category(row, self.cat_map)
        self.assertEqual(row.get("resolved_route"), "Journal Entry",
                         "Should fall back to (Entertainment, '') mapping.")

    def test_transfer_row_skips_category_lookup(self):
        row = _base_row(txn_type="Transfer")
        _resolve_category(row, self.cat_map)
        self.assertEqual(row.get("resolved_route"), "Transfer JV")
        self.assertIsNone(row.get("resolved_account"))

    def test_external_transfer_row_skips_category_lookup(self):
        row = _base_row(txn_type="External Transfer")
        _resolve_category(row, self.cat_map)
        self.assertEqual(row.get("resolved_route"), "External Transfer JE")

    def test_adjustment_row_skips_category_lookup(self):
        row = _base_row(txn_type="Adjustment")
        row["resolved_route"] = "Adjustment JE"   # set by parser
        before = row.copy()
        _resolve_category(row, self.cat_map)
        self.assertEqual(row["resolved_route"], "Adjustment JE",   # unchanged
                         "Adjustment route must not be overwritten.")

    def test_unmapped_category_leaves_no_route(self):
        row = _base_row(category="Unknown Category 123")
        _resolve_category(row, self.cat_map)
        self.assertIsNone(row.get("resolved_route"),
                          "Unmapped category should leave resolved_route unset.")


class TestPartyResolution(FrappeTestCase):
    """_resolve_party sets resolved_party from run defaults for SI/PI routes."""

    def test_sales_invoice_uses_default_customer(self):
        row = _base_row(category="Freelance", txn_type="Income")
        row["resolved_route"] = "Sales Invoice"
        run = _make_run(default_customer="Al Khashab Building Materials")
        _resolve_party(row, run)
        self.assertEqual(row["resolved_party"], "Al Khashab Building Materials")
        self.assertEqual(row["resolved_party_type"], "Customer")
        self.assertEqual(row["party_source"], "Run Default")

    def test_purchase_invoice_uses_default_supplier(self):
        row = _base_row()
        row["resolved_route"] = "Purchase Invoice"
        run = _make_run(default_supplier="Welcome Computer and Gaming Zone")
        _resolve_party(row, run)
        self.assertEqual(row["resolved_party"], "Welcome Computer and Gaming Zone")
        self.assertEqual(row["resolved_party_type"], "Supplier")

    def test_journal_entry_route_skips_party_resolution(self):
        row = _base_row()
        row["resolved_route"] = "Journal Entry"
        run = _make_run(default_customer="Al Khashab Building Materials")
        _resolve_party(row, run)
        self.assertIsNone(row.get("resolved_party"))

    def test_preview_override_takes_precedence_over_run_default(self):
        row = _base_row()
        row["resolved_route"] = "Sales Invoice"
        row["resolved_party"] = "Cute Brains"   # set by preview override
        run = _make_run(default_customer="Al Khashab Building Materials")
        _resolve_party(row, run)
        self.assertEqual(row["resolved_party"], "Cute Brains",
                         "Preview override must not be overwritten by run default.")

    def test_no_default_leaves_party_unset(self):
        row = _base_row()
        row["resolved_route"] = "Sales Invoice"
        run = _make_run(default_customer=None)
        _resolve_party(row, run)
        self.assertIsNone(row.get("resolved_party"))


class TestApplyMappingsFullPath(FrappeTestCase):
    """apply_mappings() integrates all resolution steps via mocked Cashew Settings."""

    def _run_mappings(self, rows, run=None):
        if run is None:
            run = _make_run()
        settings = _make_settings()
        with patch("cashew_integration.importer.mapping.frappe.get_single",
                   return_value=settings), \
             patch("cashew_integration.importer.mapping._lookup_erp_rate",
                   return_value=None):
            apply_mappings(rows, run)

    def test_expense_row_fully_resolved(self):
        row = _base_row(account="Petty Cash", category="Entertainment",
                        txn_type="Expense", amount=500.0)
        self._run_mappings([row])
        self.assertEqual(row["resolved_erp_account"], "Cash - CS")
        self.assertEqual(row["resolved_route"], "Journal Entry")
        self.assertEqual(row["resolved_account"], "Entertainment Expenses - CS")
        self.assertEqual(row["validation_status"], "Valid")

    def test_income_row_resolved_with_customer(self):
        row = _base_row(account="Petty Cash", category="Freelance",
                        txn_type="Income", amount=42000.0)
        run = _make_run(default_customer="Al Khashab Building Materials")
        self._run_mappings([row], run)
        self.assertEqual(row["resolved_route"], "Sales Invoice")
        self.assertEqual(row["resolved_party"], "Al Khashab Building Materials")

    def test_error_rows_are_skipped_by_mapping(self):
        row = _base_row()
        row["validation_status"] = "Error"
        self._run_mappings([row])
        self.assertIsNone(row.get("resolved_erp_account"),
                          "Error rows must not be modified by mapping.")

    def test_foreign_currency_row_exchange_rate_none_when_no_erp_rate(self):
        row = _base_row(account="NSave", currency="USD", category="Freelance",
                        txn_type="Income", amount=423.0)
        row["exchange_rate"] = None
        row["company_currency"] = "PKR"
        self._run_mappings([row])
        self.assertIsNone(row["exchange_rate"],
                          "exchange_rate must stay None when ERP has no rate for the date.")
