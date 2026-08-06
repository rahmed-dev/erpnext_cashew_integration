"""
Tests for the inline unmapped-entity resolver (f012 c014).

Covers the parts that decide WHAT gets reported, which is where a mistake is
expensive: a missed entity means the import stalls with no way to fix it from
the SPA, and a falsely reported one asks the user to map something that is
already mapped.

The collector is exercised through its per-row helpers with plain dicts rather
than through the DB, so these tests do not touch the Cashew Settings singleton.

Run:  bench --site work.local run-tests --module cashew_integration.tests.test_unmapped
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from cashew_integration.importer.unmapped import (
    CATEGORY_TYPE_ROOT_TYPES,
    _collect_account,
    _collect_category,
    _finish_account,
    _finish_category,
)


def _row(**kwargs):
    base = {
        "row_idx": 1, "raw_account": "Cash", "category": "Food", "sub_category": "",
        "txn_type": "Expense", "source_currency": "PKR", "income_flag": 0,
        "title": "", "note": "",
    }
    base.update(kwargs)
    return frappe._dict(base)


class TestAccountCollection(FrappeTestCase):
    def test_mapped_account_is_not_reported(self):
        found = {}
        _collect_account(_row(raw_account="Cash"), {"Cash"}, found)
        self.assertEqual(found, {})

    def test_unmapped_account_counts_every_row(self):
        found = {}
        for i in range(3):
            _collect_account(_row(row_idx=i, raw_account="Meezan"), set(), found)
        self.assertEqual(found["Meezan"]["row_count"], 3)

    def test_external_transfer_partner_is_reported_too(self):
        """The partner account lives only in the note — a plain raw_account scan
        misses it, but an unmapped partner blocks the row just as hard."""
        found = {}
        _collect_account(
            _row(
                raw_account="Cash",
                txn_type="External Transfer",
                note="Transferred Balance\nCash → Meezan",
            ),
            {"Cash"},
            found,
        )
        self.assertEqual(list(found), ["Meezan"])

    def test_currency_is_proposed_from_the_rows_and_conflicts_are_flagged(self):
        found = {}
        _collect_account(_row(raw_account="Wise", source_currency="USD"), set(), found)
        _collect_account(_row(raw_account="Wise", source_currency="USD"), set(), found)
        _collect_account(_row(raw_account="Wise", source_currency="EUR"), set(), found)
        entry = _finish_account(found["Wise"])
        self.assertEqual(entry["suggested_currency"], "USD")
        self.assertTrue(entry["currency_ambiguous"])

    def test_single_currency_is_not_flagged_ambiguous(self):
        found = {}
        _collect_account(_row(raw_account="Wise", source_currency="USD"), set(), found)
        self.assertFalse(_finish_account(found["Wise"])["currency_ambiguous"])


class TestCategoryCollection(FrappeTestCase):
    def test_transfer_family_rows_never_need_a_category_mapping(self):
        found = {}
        for txn_type in ("Transfer", "External Transfer", "Adjustment"):
            _collect_category(_row(txn_type=txn_type, category="Balance Correction"), {}, found)
        self.assertEqual(found, {})

    def test_category_only_mapping_covers_an_unmapped_sub_category(self):
        """The mapping engine falls back from (category, sub) to (category, ''),
        so a sub-category with no row of its own is NOT unmapped."""
        found = {}
        _collect_category(
            _row(category="Food", sub_category="Coffee"),
            {("Food", ""): {"default_account": "Food - X"}},
            found,
        )
        self.assertEqual(found, {})

    def test_unmapped_pair_is_reported_at_sub_category_granularity(self):
        found = {}
        _collect_category(_row(category="Food", sub_category="Coffee"), {}, found)
        self.assertEqual(list(found), [("Food", "Coffee")])

    def test_direction_drives_the_proposed_category_type(self):
        income, expense = {}, {}
        _collect_category(_row(category="Salary", income_flag=1), {}, income)
        _collect_category(_row(category="Food"), {}, expense)
        self.assertEqual(_finish_category(income[("Salary", "")])["suggested_category_type"], "Income")
        self.assertEqual(_finish_category(expense[("Food", "")])["suggested_category_type"], "Expense")

    def test_a_loan_type_is_never_guessed(self):
        """Loan Out / Loan In post to the balance sheet. The export cannot
        express that choice, so proposing one would silently misroute."""
        found = {}
        _collect_category(_row(category="Lent to Ali", income_flag=0), {}, found)
        self.assertNotIn(
            _finish_category(found[("Lent to Ali", "")])["suggested_category_type"],
            ("Loan Out", "Loan In"),
        )


class TestPickerFilterContract(FrappeTestCase):
    def test_root_types_match_the_validators_expectations(self):
        """The picker filter narrows to the same root_type the Cashew Category
        Mapping controller enforces on save. If these drift, the picker offers
        accounts the save will reject."""
        from cashew_integration.importer.validation import _CATEGORY_TYPE_EXPECTATIONS

        self.assertEqual(
            CATEGORY_TYPE_ROOT_TYPES,
            {k: v[0] for k, v in _CATEGORY_TYPE_EXPECTATIONS.items()},
        )
