"""
Integration tests for f001 — Cashew CSV Import.

All tests use the real work.local database (Code.Solutions company,
real ERP accounts).  Cashew Settings is configured in setUpClass and
restored in tearDownClass.  Documents created during tests are cancelled
and deleted in tearDown.

Test 1 — Parse + validate pipeline: parse a slice of the real CSV,
          apply real Cashew Settings mappings, validate rows; assert
          correct statuses and error codes.
Test 2 — Full import run → Journal Entry: create a run doc, populate
          rows, call _process() synchronously, assert a JE was submitted.
Test 3 — Idempotency re-run → Skipped: replay the same run data through
          a second run doc; every previously-posted row must be Skipped.

Run:  bench --site work.local run-tests --module cashew_integration.tests.test_integration
"""
import frappe
from frappe.tests.utils import FrappeTestCase

from cashew_integration.importer.mapping import apply_mappings
from cashew_integration.importer.parser import parse_csv
from cashew_integration.importer.validation import validate_rows_at_queue_time
from cashew_integration.importer.worker import _process

# ── real data constants ────────────────────────────────────────────────────────
COMPANY = "Code.Solutions"
COST_CENTER = "Main - CS"

ACCOUNT_MAPPINGS = [
    ("Petty Cash",  "Cash - CS",         "PKR"),
    ("NSave",       "Meezan Bank - CS",  "PKR"),
    ("Saving",      "Crypto - CS",       "PKR"),
    ("Investment",  "Earnest Money - CS","PKR"),
]

CATEGORY_MAPPINGS = [
    ("Entertainment",    "", "Journal Entry", "Entertainment Expenses - CS"),
    ("Home",             "", "Journal Entry", "Office Maintenance Expenses - CS"),
    ("Family",           "", "Journal Entry", "Administrative Expenses - CS"),
    ("Internet Expense", "", "Journal Entry", "Utility Expenses - CS"),
    ("Bills & Fees",     "", "Journal Entry", "Miscellaneous Expenses - CS"),
    ("Bank Charges",     "", "Journal Entry", "Write Off - CS"),
    ("Fuel",             "", "Journal Entry", "Travel Expenses - CS"),
    ("Grocery",          "", "Journal Entry", "Administrative Expenses - CS"),
    ("Cursor",           "", "Journal Entry", "Miscellaneous Expenses - CS"),
    ("Freelance",        "", "Sales Invoice",  "Service - CS"),
    ("Salary",           "", "Sales Invoice",  "Service - CS"),
]

# A minimal CSV covering: 2 expense (JE), 1 transfer pair, 1 unmapped category
INTEGRATION_CSV = (
    "account,amount,currency,title,note,date,income,type,"
    "category name,subcategory name,color,icon,emoji,budget,objective\n"
    # expense rows — Petty Cash PKR → Journal Entry
    "Petty Cash,-2240.0,PKR,Fast food,,2026-04-08 19:00:18.000,false,null,"
    "Entertainment,,0xff2196f3,popcorn.png,,,\n"
    "Petty Cash,-4000.0,PKR,,,2026-04-06 19:49:51.000,false,null,"
    "Home,,,,,,\n"
    # internal transfer pair — PKR same-currency
    'Saving,120000.0,PKR,Saving,"Transferred Balance\nPetty Cash \u2192 Saving",'
    "2026-04-08 20:27:31.000,true,null,Balance Correction,,,,,,\n"
    'Petty Cash,-120000.0,PKR,Saving,"Transferred Balance\nPetty Cash \u2192 Saving",'
    "2026-04-08 20:27:30.000,false,null,Balance Correction,,,,,,\n"
    # unmapped category — should get MAPPING_NOT_FOUND at queue time
    "Petty Cash,-100.0,PKR,test,,2026-04-01 10:00:00.000,false,null,"
    "UnknownCat123,,,,,,\n"
)


class TestImportIntegration(FrappeTestCase):

    # ── class-level setup: configure Cashew Settings once ─────────────────────

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._original_acct_rows = []
        cls._original_cat_rows  = []

        settings = frappe.get_single("Cashew Settings")
        # Save original child-table rows so tearDownClass can restore
        cls._original_acct_rows = [r.as_dict() for r in settings.cashew_account_mapping]
        cls._original_cat_rows  = [r.as_dict() for r in settings.cashew_category_mapping]

        settings.cashew_account_mapping = []
        settings.cashew_category_mapping = []
        for cashew_name, erp_acct, currency in ACCOUNT_MAPPINGS:
            settings.append("cashew_account_mapping", {
                "cashew_account_name": cashew_name,
                "erp_account":         erp_acct,
                "account_currency":    currency,
                "is_active":           1,
            })
        for cat, sub, route, acct in CATEGORY_MAPPINGS:
            settings.append("cashew_category_mapping", {
                "cashew_category":     cat,
                "cashew_sub_category": sub,
                "default_route":       route,
                "default_account":     acct,
                "is_active":           1,
            })
        settings.save(ignore_permissions=True)
        frappe.db.commit()

        # Purge any leftover test runs from prior invocations so idempotency
        # guard doesn't fire on the same row hashes.
        cls._purge_test_runs()

    @classmethod
    def tearDownClass(cls):
        settings = frappe.get_single("Cashew Settings")
        settings.cashew_account_mapping = []
        settings.cashew_category_mapping = []
        for row in cls._original_acct_rows:
            settings.append("cashew_account_mapping", row)
        for row in cls._original_cat_rows:
            settings.append("cashew_category_mapping", row)
        settings.save(ignore_permissions=True)
        frappe.db.commit()
        super().tearDownClass()

    @classmethod
    def _purge_test_runs(cls):
        """Delete all Cashew Import Runs (+ their rows) for the test company.
        Called in setUpClass to guarantee a clean slate regardless of prior runs."""
        for run_name in frappe.get_all(
            "Cashew Import Run", filters={"company": COMPANY}, pluck="name"
        ):
            frappe.db.delete("Cashew Import Row", {"parent": run_name})
            frappe.db.delete("Cashew Import Run", {"name": run_name})
        frappe.db.commit()

    def setUp(self):
        self._docs_to_cleanup = []   # (doctype, name) pairs

    def tearDown(self):
        for doctype, name in reversed(self._docs_to_cleanup):
            try:
                doc = frappe.get_doc(doctype, name)
                if hasattr(doc, "docstatus") and doc.docstatus == 1:
                    doc.cancel()
                    frappe.db.commit()
                frappe.db.delete(doctype, {"name": name})
            except Exception:
                pass
        frappe.db.commit()

    def _track(self, doctype, name):
        self._docs_to_cleanup.append((doctype, name))

    # ── helpers ───────────────────────────────────────────────────────────────

    def _parse_and_map(self, csv_bytes=None):
        """Parse INTEGRATION_CSV and apply Cashew Settings mappings."""
        if csv_bytes is None:
            csv_bytes = INTEGRATION_CSV.encode("utf-8")
        rows = parse_csv(csv_bytes, "PKR")
        run_mock = frappe.get_doc({
            "doctype":            "Cashew Import Run",
            "company":            COMPANY,
            "default_customer":   "Al Khashab Building Materials",
            "default_supplier":   None,
            "expense_threshold":  0,
        })
        run_mock.company_currency = "PKR"
        apply_mappings(rows, run_mock)
        return rows, run_mock

    def _create_run(self, rows):
        """Persist a Cashew Import Run with child rows to the DB."""
        run = frappe.get_doc({
            "doctype":               "Cashew Import Run",
            "company":               COMPANY,
            "default_customer":      "Al Khashab Building Materials",
            "default_mode_of_payment": "Cash",
            "expense_threshold":     0,
            "status":                "Queued",
            "rows_total":            len(rows),
        })
        for row in rows:
            child = run.append("import_rows", {})
            skip = {"income_flag"}
            for k, v in row.items():
                if k.startswith("_") or k in skip:
                    continue
                try:
                    child.set(k, v)
                except Exception:
                    pass
        run.insert(ignore_permissions=True, ignore_mandatory=True)
        frappe.db.commit()
        self._track("Cashew Import Run", run.name)
        return run

    # ── Test 1: parse + validate pipeline ────────────────────────────────────

    def test_parse_and_validate_all_rows_classified(self):
        """Every row in INTEGRATION_CSV gets a txn_type after parsing."""
        rows, _ = self._parse_and_map()
        for row in rows:
            self.assertIn(row.get("txn_type"),
                          ("Income", "Expense", "Transfer", "External Transfer",
                           "Adjustment"),
                          f"Row {row['row_idx']} has unexpected txn_type.")

    def test_expense_rows_get_resolved_route_journal_entry(self):
        rows, _ = self._parse_and_map()
        expense_rows = [r for r in rows if r.get("category") == "Entertainment"]
        self.assertTrue(expense_rows, "No Entertainment rows found.")
        for row in expense_rows:
            self.assertEqual(row.get("resolved_route"), "Journal Entry")
            self.assertEqual(row.get("resolved_account"), "Entertainment Expenses - CS")
            self.assertEqual(row.get("resolved_erp_account"), "Cash - CS")

    def test_transfer_pair_resolved_and_linked(self):
        rows, _ = self._parse_and_map()
        transfer_rows = [r for r in rows if r.get("txn_type") == "Transfer"]
        self.assertEqual(len(transfer_rows), 2,
                         "Exactly 2 Transfer legs expected for the PKR pair.")
        pair_idxs = {r["row_idx"] for r in transfer_rows}
        for row in transfer_rows:
            self.assertIn(row.get("transfer_pair_row_idx"), pair_idxs,
                          "Transfer leg must point to the other leg's row_idx.")

    def test_unmapped_category_blocked_at_queue_time(self):
        rows, _ = self._parse_and_map()
        # UnknownCat123 row enters mapping with no route; queue-time validation catches it
        validate_rows_at_queue_time(rows)
        unknown_rows = [r for r in rows if r.get("category") == "UnknownCat123"]
        self.assertTrue(unknown_rows, "UnknownCat123 row should exist.")
        for row in unknown_rows:
            self.assertEqual(row["validation_status"], "Error")
            self.assertEqual(row["validation_error_code"], "MAPPING_NOT_FOUND")

    # ── Test 2: full run → Journal Entry created ──────────────────────────────

    def test_full_import_run_produces_journal_entries(self):
        """_process() submits a JE for each expense row and marks run Completed."""
        rows, _ = self._parse_and_map()

        # Keep only the 2 expense JE rows (skip transfer + unknown to isolate JE posting)
        je_rows = [r for r in rows
                   if r.get("resolved_route") == "Journal Entry"
                   and r["validation_status"] == "Valid"]
        self.assertGreaterEqual(len(je_rows), 1, "Need at least one JE row for this test.")

        run = self._create_run(je_rows)
        _process(run.name)

        run.reload()
        self.assertEqual(run.status, "Completed",
                         f"Run should be Completed, got '{run.status}'.")
        self.assertGreaterEqual(run.rows_posted, 1,
                                "At least one row must be posted.")
        self.assertEqual(run.rows_failed, 0,
                         f"{run.rows_failed} row(s) failed unexpectedly.")

        # Verify actual JE documents exist and are submitted
        for child in run.import_rows:
            if child.posted_doctype == "Journal Entry":
                self._track("Journal Entry", child.posted_docname)
                je = frappe.get_doc("Journal Entry", child.posted_docname)
                self.assertEqual(je.docstatus, 1,
                                 f"JE {je.name} must be submitted (docstatus=1).")
                self.assertEqual(je.company, COMPANY)
                self.assertEqual(je.cashew_import_run, run.name)
                self.assertIsNotNone(je.cashew_row_hash)

    # ── Test 3: idempotency re-run → all rows Skipped ─────────────────────────

    def test_idempotency_rerun_marks_rows_skipped(self):
        """A second run with identical row hashes must mark every row as Skipped."""
        rows, _ = self._parse_and_map()
        je_rows = [r for r in rows
                   if r.get("resolved_route") == "Journal Entry"
                   and r["validation_status"] == "Valid"]

        # First run — posts JEs
        run1 = self._create_run(je_rows)
        _process(run1.name)
        run1.reload()
        self.assertEqual(run1.status, "Completed")

        # Track JEs for cleanup
        for child in run1.import_rows:
            if child.posted_doctype and child.posted_docname:
                self._track(child.posted_doctype, child.posted_docname)

        # Second run — same rows, same hashes
        run2 = self._create_run(je_rows)
        _process(run2.name)
        run2.reload()

        self.assertEqual(run2.status, "Completed",
                         f"Second run should be Completed, got '{run2.status}'.")
        self.assertEqual(run2.rows_skipped, len(je_rows),
                         f"All {len(je_rows)} rows must be Skipped on re-run; "
                         f"got {run2.rows_skipped} skipped.")
        self.assertEqual(run2.rows_posted, 0,
                         "No rows should be posted on re-run.")

        for child in run2.import_rows:
            self.assertEqual(child.validation_status, "Skipped")
            self.assertEqual(child.is_duplicate, 1)
            self.assertIsNotNone(child.posted_docname,
                                 "Skipped rows must reference the original doc.")
