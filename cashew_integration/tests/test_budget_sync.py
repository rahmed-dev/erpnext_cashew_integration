"""
Tests for the budgets-only sync (f012 c015) and the invoice KPIs (f012 c003).

The sync's whole value is that it is re-run by hand after editing a budget in
Cashew, so what it reports about a re-run is the thing worth testing: a second
pass over an unchanged backup must say "unchanged", not "imported", and must not
touch the document. The mapping tables are patched rather than written into
Cashew Settings — the gate itself is already covered by test_budgets.py, and a
test that mutates the singleton would leak into every other test on the site.

Run:  bench --site work.local run-tests --module cashew_integration.tests.test_budget_sync
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from cashew_integration.api import _invoice_kpis
from cashew_integration.importer import budgets as budgets_module

BUDGET_PK = "test-c015-budget"


def _a_company_and_account():
    """Any real company plus one of its expense accounts, or (None, None)."""
    company = frappe.db.get_value("Company", {}, "name")
    if not company:
        return None, None
    account = frappe.db.get_value(
        "Account", {"company": company, "root_type": "Expense", "is_group": 0}, "name"
    )
    return company, account


def _drop_budget():
    """Delete through the ORM, NOT `frappe.db.delete`.

    A raw delete on the parent leaves the scope child rows behind, and the next
    import loads them back under the same name — the budget then appears to have
    every category twice and every re-run reports a change that never happened.
    """
    if frappe.db.exists("Cashew Budget", BUDGET_PK):
        frappe.delete_doc("Cashew Budget", BUDGET_PK, force=True, ignore_permissions=True)


def _budget(**overrides):
    base = {
        "budget_pk": BUDGET_PK,
        "budget_name": "Food outdoor",
        "amount": 10000.0,
        "is_income": 0,
        "is_archived": 0,
        "is_pinned": 1,
        "start_date": "2025-08-01",
        "reoccurrence": "Monthly",
        "period_length": 1,
        "category_scope": [{"pk": "5", "category": "Entertainment", "sub_category": ""}],
        "category_exclude": [],
        "wallet_scope": [],
    }
    base.update(overrides)
    return base


class TestBudgetSyncOutcomes(FrappeTestCase):
    def setUp(self):
        self.company, self.account = _a_company_and_account()
        if not self.account:
            self.skipTest("no company with an expense account on this site")
        _drop_budget()
        self.category_map = {
            ("Entertainment", ""): {"default_account": self.account, "category_type": "Expense"},
        }
        self.account_map = {"Petty Cash": self.account}

    def tearDown(self):
        _drop_budget()

    def _import(self, budget):
        with patch.object(budgets_module, "build_category_type_map", return_value=self.category_map), \
             patch.object(budgets_module, "_account_name_map", return_value=self.account_map):
            return budgets_module.import_budgets([budget], self.company)

    def test_a_first_sync_reports_created(self):
        summary = self._import(_budget())
        self.assertEqual(summary["created"], [BUDGET_PK])
        self.assertEqual(summary["updated"], [])
        self.assertEqual(summary["unchanged"], [])

    def test_a_second_sync_of_the_same_backup_reports_unchanged(self):
        """The action is meant to be re-run. Reporting a change every time makes
        the report useless for answering 'did my edit land'."""
        self._import(_budget())
        summary = self._import(_budget())
        self.assertEqual(summary["unchanged"], [BUDGET_PK])
        self.assertEqual(summary["created"], [])

    def test_an_unchanged_sync_does_not_touch_the_document(self):
        """A no-op save would put an edit in the version trail that never happened."""
        self._import(_budget())
        before = frappe.db.get_value("Cashew Budget", BUDGET_PK, "modified")
        self._import(_budget())
        self.assertEqual(frappe.db.get_value("Cashew Budget", BUDGET_PK, "modified"), before)

    def test_an_edited_amount_reports_updated(self):
        self._import(_budget())
        summary = self._import(_budget(amount=12500.0))
        self.assertEqual(summary["updated"], [BUDGET_PK])
        self.assertEqual(
            frappe.db.get_value("Cashew Budget", BUDGET_PK, "amount"), 12500.0
        )

    def test_a_scope_change_alone_reports_updated(self):
        """Scope lives in child tables; comparing only the parent's fields would
        miss a category added to the budget in Cashew."""
        self._import(_budget())
        self.category_map[("Fuel", "")] = {
            "default_account": self.account, "category_type": "Expense",
        }
        summary = self._import(_budget(category_scope=[
            {"pk": "5", "category": "Entertainment", "sub_category": ""},
            {"pk": "9", "category": "Fuel", "sub_category": ""},
        ]))
        self.assertEqual(summary["updated"], [BUDGET_PK])

    def test_archiving_in_cashew_disables_the_budget(self):
        self._import(_budget())
        summary = self._import(_budget(is_archived=1))
        self.assertEqual(summary["updated"], [BUDGET_PK])
        self.assertEqual(frappe.db.get_value("Cashew Budget", BUDGET_PK, "disabled"), 1)

    def test_an_unmapped_scope_is_reported_not_imported(self):
        summary = self._import(_budget(category_scope=[
            {"pk": "77", "category": "Travel", "sub_category": ""},
        ]))
        self.assertEqual(summary["created"], [])
        self.assertEqual(summary["skipped"][0]["budget_pk"], BUDGET_PK)
        self.assertFalse(frappe.db.exists("Cashew Budget", BUDGET_PK))


class TestInvoiceKpis(FrappeTestCase):
    def setUp(self):
        self.company = frappe.db.get_value("Company", {}, "name")
        if not self.company:
            self.skipTest("no company on this site")

    def test_both_invoice_doctypes_are_reported(self):
        kpis = _invoice_kpis(self.company, "2020-01-01", "2020-01-31")
        self.assertEqual(set(kpis), {"sales", "purchase"})

    def test_an_empty_period_is_zero_not_none(self):
        """None means 'you may not read this doctype'. A quiet period is a zero,
        and the two must not render the same."""
        kpis = _invoice_kpis(self.company, "1990-01-01", "1990-01-31")
        for block in kpis.values():
            if block is None:
                continue
            self.assertEqual(block["count"], 0)
            self.assertEqual(block["amount"], 0.0)

    def test_no_read_permission_reports_none(self):
        with patch("frappe.has_permission", return_value=False):
            kpis = _invoice_kpis(self.company, "2020-01-01", "2020-01-31")
        self.assertIsNone(kpis["sales"])
        self.assertIsNone(kpis["purchase"])
