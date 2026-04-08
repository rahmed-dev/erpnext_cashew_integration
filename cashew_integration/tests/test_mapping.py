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
    _lookup_online_rate,
    _lookup_erp_rate,
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
        self.assertEqual(row.get("resolved_income_account"), "Service - CS")
        self.assertIsNone(row.get("resolved_expense_account"))

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
        self.assertEqual(row.get("resolved_expense_account"), "Entertainment Expenses - CS")
        self.assertIsNone(row.get("resolved_income_account"))
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

    def test_foreign_currency_row_exchange_rate_prefilled_when_erp_rate_found(self):
        """When _lookup_erp_rate returns a rate, exchange_rate and base_amount are set."""
        row = _base_row(account="NSave", currency="USD", category="Freelance",
                        txn_type="Income", amount=423.0)
        row["exchange_rate"] = None
        row["company_currency"] = "PKR"

        settings = _make_settings()
        with patch("cashew_integration.importer.mapping.frappe.get_single",
                   return_value=settings), \
             patch("cashew_integration.importer.mapping._lookup_erp_rate",
                   return_value=280.5):
            apply_mappings([row], _make_run())

        self.assertEqual(row["exchange_rate"], 280.5,
                         "exchange_rate must be set from ERP rate when one exists.")
        self.assertAlmostEqual(row["base_amount"], round(423.0 * 280.5, 2),
                               places=2,
                               msg="base_amount must equal raw_amount * exchange_rate.")

    def test_external_transfer_foreign_currency_prefills_exchange_rate(self):
        row = _base_row(account="NSave", currency="USD", txn_type="External Transfer", amount=50.0)
        row["note"] = "Transferred Balance\\nNSave → ExternalBank"
        row["exchange_rate"] = None
        row["company_currency"] = "PKR"

        settings = _make_settings()
        with patch("cashew_integration.importer.mapping.frappe.get_single", return_value=settings), \
             patch("cashew_integration.importer.mapping._lookup_erp_rate", return_value=279.9):
            apply_mappings([row], _make_run())

        self.assertEqual(row["exchange_rate"], 279.9)
        self.assertAlmostEqual(row["base_amount"], round(50.0 * 279.9, 2), places=2)


class TestMappingFiltering(FrappeTestCase):
    """Inactive mapping rows are excluded; unresolved categories are diagnosable."""

    def test_inactive_account_row_excluded_from_map(self):
        settings = MagicMock()
        settings.cashew_account_mapping = [
            MagicMock(cashew_account_name="Active",   erp_account="Cash - CS",
                      account_currency="PKR", is_active=True),
            MagicMock(cashew_account_name="Inactive", erp_account="Meezan Bank - CS",
                      account_currency="PKR", is_active=False),
        ]
        m = _build_account_map(settings)
        self.assertIn("Active", m,
                      "Active account row must appear in the account map.")
        self.assertNotIn("Inactive", m,
                         "Inactive account row must be excluded from the account map.")

    def test_inactive_category_row_excluded_from_map(self):
        settings = MagicMock()
        settings.cashew_category_mapping = [
            MagicMock(cashew_category="Active Cat",   cashew_sub_category="",
                      default_route="Journal Entry", default_account="X - CS",
                      is_active=True),
            MagicMock(cashew_category="Inactive Cat", cashew_sub_category="",
                      default_route="Journal Entry", default_account="Y - CS",
                      is_active=False),
        ]
        m = _build_category_map(settings)
        self.assertIn(("Active Cat", ""), m,
                      "Active category row must appear in the category map.")
        self.assertNotIn(("Inactive Cat", ""), m,
                         "Inactive category row must be excluded from the category map.")

    def test_unresolved_category_leaves_route_and_account_unset(self):
        """A category with no mapping leaves resolved_route/resolved_account unset.
        The row stays Valid at mapping time; queue-time validation fires MAPPING_NOT_FOUND."""
        row = _base_row(category="NoSuchCategory123", txn_type="Expense")
        settings = _make_settings()
        with patch("cashew_integration.importer.mapping.frappe.get_single",
                   return_value=settings), \
             patch("cashew_integration.importer.mapping._lookup_erp_rate",
                   return_value=None):
            apply_mappings([row], _make_run())

        self.assertIsNone(row.get("resolved_route"),
                          "Unknown category must leave resolved_route unset.")
        self.assertIsNone(row.get("resolved_account"),
                          "Unknown category must leave resolved_account unset.")
        self.assertEqual(row["validation_status"], "Valid",
                         "Mapping gaps surface at queue-time, not at mapping time.")


class TestExchangeRateLookupFallbacks(FrappeTestCase):
    """_lookup_erp_rate should fallback when for_buying is unavailable."""

    @patch("erpnext.setup.utils.get_exchange_rate")
    def test_lookup_falls_back_to_generic_rate(self, m_get_rate):
        # first call: for_buying -> missing, second call: generic -> found
        m_get_rate.side_effect = [None, 279.25]
        rate = _lookup_erp_rate("USD", "PKR", "2026-04-09")
        self.assertEqual(rate, 279.25)

    @patch("erpnext.setup.utils.get_exchange_rate")
    def test_lookup_falls_back_to_inverse_rate(self, m_get_rate):
        # for_buying -> none, generic direct -> none, generic inverse -> found
        m_get_rate.side_effect = [None, None, 0.0036]
        rate = _lookup_erp_rate("USD", "PKR", "2026-04-09")
        self.assertAlmostEqual(rate, round(1 / 0.0036, 10), places=10)

    @patch("cashew_integration.importer.mapping._lookup_online_rate")
    @patch("erpnext.setup.utils.get_exchange_rate")
    def test_lookup_falls_back_to_online_rate(self, m_get_rate, m_online):
        m_get_rate.side_effect = [None, None, None]
        m_online.return_value = 281.4
        rate = _lookup_erp_rate("USD", "PKR", "2026-04-09")
        self.assertEqual(rate, 281.4)


class TestOnlineRateLookup(FrappeTestCase):
    @patch("cashew_integration.importer.mapping.requests.get")
    @patch("cashew_integration.importer.mapping.frappe.cache")
    def test_online_lookup_reads_provider_and_caches(self, m_cache_factory, m_get):
        cache = MagicMock()
        cache.get_value.return_value = None
        m_cache_factory.return_value = cache

        resp = MagicMock()
        resp.json.return_value = {"rates": {"PKR": 279.77}}
        resp.raise_for_status.return_value = None
        m_get.return_value = resp

        rate = _lookup_online_rate("USD", "PKR", "2026-04-09")
        self.assertEqual(rate, 279.77)
        cache.set_value.assert_called_once()

    @patch("cashew_integration.importer.mapping.requests.get")
    @patch("cashew_integration.importer.mapping.frappe.cache")
    def test_online_lookup_uses_secondary_provider_when_primary_fails(self, m_cache_factory, m_get):
        cache = MagicMock()
        cache.get_value.return_value = None
        m_cache_factory.return_value = cache

        first_resp = MagicMock()
        first_resp.raise_for_status.side_effect = Exception("primary down")

        second_resp = MagicMock()
        second_resp.raise_for_status.return_value = None
        second_resp.json.return_value = {"rates": {"PKR": 278.11}}

        m_get.side_effect = [first_resp, second_resp]

        rate = _lookup_online_rate("USD", "PKR", "2026-04-09")
        self.assertEqual(rate, 278.11)
