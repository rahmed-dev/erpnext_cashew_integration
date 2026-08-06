"""
Tests for the import-integrity fixes.

Each test pins one defect found by the 2026-08-07 reconciliation of the live
site against its Cashew Import Runs — see
``.fb/system-arch/import-integrity-2026-08-07.md``.

Run:  bench --site work.local run-tests --module cashew_integration.tests.test_integrity
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from cashew_integration.importer.posting import post_transfer_pair
from cashew_integration.importer.reconcile import _counter_drift

COMPANY = "Code.Solutions"


def _transfer_leg(row_idx, currency, amount, income):
    return {
        "row_idx": row_idx,
        "txn_date": "2026-05-14",
        "txn_type": "Transfer",
        "source_currency": currency,
        "raw_amount": amount,
        "income_flag": "true" if income else "false",
        "raw_account": f"Account {row_idx}",
        "note": "Transferred Balance\nNSave → Elevate Pay",
        "source_hash": f"hash-{row_idx}",
        "resolved_erp_account": None,
    }


class TestSameCurrencyForeignTransfer(FrappeTestCase):
    """A transfer between two accounts that share a *foreign* currency has no
    counter-leg to imply a rate from. Booking it 1:1 pushes a foreign amount into
    a company-currency column, which is how Elevate Pay ended up flat in USD and
    -1,238.85 in PKR."""

    def test_no_rate_available_errors_both_legs_instead_of_posting(self):
        company_currency = frappe.get_cached_value(
            "Company", COMPANY, "default_currency"
        )
        foreign = "USD" if company_currency != "USD" else "EUR"

        source = _transfer_leg(20, foreign, 4.50, income=False)
        dest = _transfer_leg(21, foreign, 4.50, income=True)
        run = frappe._dict(company=COMPANY, name="TEST-RUN", je_rounding_tolerance=0.01)

        with patch("cashew_integration.importer.mapping._lookup_erp_rate",
                   return_value=None):
            doctype, docname = post_transfer_pair(source, dest, run)

        self.assertEqual((doctype, docname), ("", ""))
        for leg in (source, dest):
            self.assertEqual(leg["validation_status"], "Error")
            self.assertEqual(leg["validation_error_code"], "TRANSFER_RATE_UNAVAILABLE")

    def test_available_rate_is_applied_to_both_legs(self):
        """The whole point of the fix: 4.50 USD must land as ~1,246.50 PKR, not
        as 4.50 PKR."""
        company_currency = frappe.get_cached_value(
            "Company", COMPANY, "default_currency"
        )
        foreign = "USD" if company_currency != "USD" else "EUR"

        # Unequal amounts so the pair bails on the tolerance check before insert;
        # the rate is stamped before that check runs.
        source = _transfer_leg(20, foreign, 4.50, income=False)
        dest = _transfer_leg(21, foreign, 5.00, income=True)
        run = frappe._dict(company=COMPANY, name="TEST-RUN", je_rounding_tolerance=0.01)

        with patch("cashew_integration.importer.mapping._lookup_erp_rate",
                   return_value=277.0):
            post_transfer_pair(source, dest, run)

        self.assertEqual(source["exchange_rate"], 277.0)
        self.assertEqual(source["base_amount"], 1246.50)
        self.assertEqual(dest["base_amount"], 1385.00)

    def test_company_currency_pair_still_takes_the_one_to_one_path(self):
        """Both legs in company currency is the case 1:1 was always right for —
        the fix must not have made it require a rate lookup."""
        company_currency = frappe.get_cached_value(
            "Company", COMPANY, "default_currency"
        )
        # Deliberately imbalanced so the pair bails out on the tolerance check
        # rather than reaching insert() — the rate branch and the rate stamping
        # both happen before that, which is what this test is about.
        source = _transfer_leg(1, company_currency, 100.0, income=False)
        dest = _transfer_leg(2, company_currency, 250.0, income=True)
        run = frappe._dict(company=COMPANY, name="TEST-RUN", je_rounding_tolerance=0.01)

        doctype, _docname = post_transfer_pair(source, dest, run)

        self.assertEqual(doctype, "")
        self.assertEqual(
            source["validation_error_code"], "TRANSFER_JV_IMBALANCE",
            "must fail on the imbalance, not on a missing rate",
        )
        self.assertEqual(source["exchange_rate"], 1.0)
        self.assertEqual(source["base_amount"], 100.0)
        self.assertEqual(dest["base_amount"], 250.0)


class TestNewRunCannotClaimHistory(FrappeTestCase):
    """Desk's Duplicate copied status, counters and timestamps verbatim, which
    produced a run claiming 54 posted rows with a `started_on` earlier than its
    own `creation`."""

    def test_validate_resets_lifecycle_fields_on_a_new_run(self):
        run = frappe.get_doc({
            "doctype": "Cashew Import Run",
            "company": COMPANY,
            "source_type": "CSV",
            "source_file": "/private/files/does-not-exist.csv",
            "status": "Reverted",
            "rows_total": 54,
            "rows_posted": 54,
            "rows_valid": 54,
            "started_on": "2026-05-03 10:19:57",
            "finished_on": "2026-05-03 10:24:44",
        })
        run.validate()

        self.assertEqual(run.status, "Draft")
        self.assertEqual(run.rows_total, 0)
        self.assertEqual(run.rows_posted, 0)
        self.assertEqual(run.rows_valid, 0)
        self.assertIsNone(run.started_on)
        self.assertIsNone(run.finished_on)


class TestCounterDrift(FrappeTestCase):

    def test_reverted_run_claiming_posted_rows_but_owning_none_is_drift(self):
        """The phantom-duplicate signature: no child rows, no documents, yet
        rows_posted=54 inherited from the run it was copied from."""
        run = frappe._dict(
            status="Reverted", rows_total=0, rows_valid=0,
            rows_failed=0, rows_skipped=0, rows_posted=54,
        )
        result = _counter_drift(run, rows=[])

        self.assertTrue(result["drift"])
        self.assertEqual(result["actual"]["rows_total"], 0)

    def test_reverted_run_with_rows_is_allowed_to_keep_its_lifetime_count(self):
        rows = [
            frappe._dict(validation_status="Valid", posted_docname=None),
            frappe._dict(validation_status="Valid", posted_docname=None),
        ]
        run = frappe._dict(
            status="Reverted", rows_total=2, rows_valid=2,
            rows_failed=0, rows_skipped=0, rows_posted=2,
        )
        result = _counter_drift(run, rows)

        self.assertFalse(result["drift"])

    def test_missing_child_rows_on_a_completed_run_is_drift(self):
        run = frappe._dict(
            status="Completed", rows_total=43, rows_valid=43,
            rows_failed=0, rows_skipped=0, rows_posted=43,
        )
        result = _counter_drift(run, rows=[])

        self.assertTrue(result["drift"])
