"""
Tests for resync of Cashew transactions edited after they were imported.

Pins the defect found by the 2026-08-07 Petty Cash reconciliation: a loan edited in
Cashew from 150,000.00 to 148,674.00 stayed in the ledger at 150,000.00, because the
reader windowed on ``date_created`` only and idempotency keyed on ``source_hash``
only. See ``.fb/system-arch/import-integrity-fixes-2026-08-07.md``.

Run:  bench --site work.local run-tests --module cashew_integration.tests.test_resync
"""

import sqlite3
import tempfile
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from cashew_integration.importer.resync import (
    RESYNCED,
    SUPERSEDED,
    _period_closed,
    apply_resync,
    mark_changed_rows,
)
from cashew_integration.importer.sqlite_reader import read_sqlite

COMPANY = "Code.Solutions"

# 2026-06-29 15:43:08 UTC and 2026-07-07 05:55:38 UTC — the real timestamps.
CREATED = 1782747788
MODIFIED = 1783403738


def _build_sqlite(amount: float, modified: int | None) -> bytes:
    """Minimal Cashew-shaped DB with one paid transaction."""
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.executescript(
        """
        CREATE TABLE wallets (wallet_pk TEXT, name TEXT, currency TEXT);
        CREATE TABLE categories (category_pk TEXT, name TEXT);
        CREATE TABLE transactions (
            transaction_pk TEXT, name TEXT, amount REAL, note TEXT, income INTEGER,
            date_created INTEGER, date_time_modified INTEGER,
            paired_transaction_fk TEXT, wallet_fk TEXT,
            category_fk TEXT, sub_category_fk TEXT, paid INTEGER
        );
        INSERT INTO wallets VALUES ('w1', 'Petty Cash', 'pkr');
        INSERT INTO categories VALUES ('c1', 'Loan');
        """
    )
    conn.execute(
        "INSERT INTO transactions VALUES ('pk-1','Loan',?,'',0,?,?,NULL,'w1','c1',NULL,1)",
        (-abs(amount), CREATED, modified),
    )
    conn.commit()
    conn.close()
    return open(tmp.name, "rb").read()


class TestEditedTransactionIsVisible(FrappeTestCase):
    """The reader windowed on date_created alone, so an edit to an older transaction
    fell outside every later window and was never seen again."""

    def test_row_edited_in_window_is_returned_even_though_created_earlier(self):
        content = _build_sqlite(148674.0, MODIFIED)
        rows = read_sqlite(content, "PKR", from_date="2026-07-01", to_date="2026-07-31")

        self.assertEqual(len(rows), 1, "edit in-window must resurface the transaction")
        self.assertEqual(
            rows[0]["txn_date"], "2026-06-29",
            "posting date must stay the transaction's real date, not the edit date",
        )

    def test_row_created_in_window_is_still_returned(self):
        content = _build_sqlite(148674.0, MODIFIED)
        rows = read_sqlite(content, "PKR", from_date="2026-06-01", to_date="2026-06-30")
        self.assertEqual(len(rows), 1)

    def test_unedited_row_windows_exactly_as_before(self):
        """date_time_modified NULL is the common case; behaviour must not change."""
        content = _build_sqlite(148674.0, None)
        self.assertEqual(
            len(read_sqlite(content, "PKR", from_date="2026-07-01", to_date="2026-07-31")),
            0,
        )
        self.assertEqual(
            len(read_sqlite(content, "PKR", from_date="2026-06-01", to_date="2026-06-30")),
            1,
        )

    def test_source_pk_is_persisted_and_stays_out_of_the_hash(self):
        """The pk is stable across edits and the hash is not — that difference is the
        whole detection mechanism, so the pk must never enter the hash."""
        before = read_sqlite(_build_sqlite(150000.0, CREATED), "PKR")[0]
        after = read_sqlite(_build_sqlite(148674.0, MODIFIED), "PKR")[0]

        self.assertEqual(before["source_pk"], after["source_pk"])
        self.assertNotEqual(
            before["source_hash"], after["source_hash"],
            "an edited amount must change the content hash",
        )
        self.assertEqual(after["source_modified"], "2026-07-07 10:55:38")


class TestChangeDetection(FrappeTestCase):

    def _prior(self, source_hash):
        return [{
            "name": "ROW-OLD", "source_pk": "pk-1", "source_hash": source_hash,
            "row_idx": 7, "posted_doctype": "Journal Entry",
            "posted_docname": "ACC-JV-TEST-0001", "parent": "RUN-OLD",
        }]

    def test_same_pk_different_hash_is_tagged_for_resync(self):
        rows = [{"row_idx": 1, "source_pk": "pk-1", "source_hash": "new-hash",
                 "validation_status": "Valid"}]
        run = frappe._dict(company=COMPANY, name="RUN-NEW")

        with patch("cashew_integration.importer.resync.frappe.db.sql",
                   return_value=self._prior("old-hash")):
            tagged = mark_changed_rows(rows, run)

        self.assertEqual(tagged, 1)
        self.assertEqual(rows[0]["_resync_of"]["posted_docname"], "ACC-JV-TEST-0001")

    def test_same_pk_same_hash_is_left_for_the_duplicate_guard(self):
        rows = [{"row_idx": 1, "source_pk": "pk-1", "source_hash": "same",
                 "validation_status": "Valid"}]
        run = frappe._dict(company=COMPANY, name="RUN-NEW")

        with patch("cashew_integration.importer.resync.frappe.db.sql",
                   return_value=self._prior("same")):
            tagged = mark_changed_rows(rows, run)

        self.assertEqual(tagged, 0)
        self.assertNotIn("_resync_of", rows[0])

    def test_csv_era_row_without_a_pk_is_untouched(self):
        rows = [{"row_idx": 1, "source_pk": None, "source_hash": "h",
                 "validation_status": "Valid"}]
        run = frappe._dict(company=COMPANY, name="RUN-NEW")
        self.assertEqual(mark_changed_rows(rows, run), 0)


class TestResyncGuards(FrappeTestCase):
    """A routine import can now cancel submitted GL, so refusing safely matters more
    than succeeding."""

    def test_closed_period_errors_the_row_and_writes_nothing(self):
        row = {"row_idx": 1, "validation_status": "Valid",
               "_resync_of": {"name": "ROW-OLD", "posted_doctype": "Journal Entry",
                              "posted_docname": "ACC-JV-TEST-0001", "row_idx": 7,
                              "parent": "RUN-OLD"}}
        run = frappe._dict(company=COMPANY, name="RUN-NEW")

        with patch("cashew_integration.importer.resync.frappe.db.exists",
                   return_value=True), \
             patch("cashew_integration.importer.resync.frappe.db.get_value",
                   return_value=(1, "2026-06-29")), \
             patch("cashew_integration.importer.resync._period_closed",
                   return_value="disabled Fiscal Year 2026"), \
             patch("cashew_integration.importer.posting.post_row") as posted:
            doctype, docname = apply_resync(row, run)

        self.assertEqual((doctype, docname), ("", ""))
        self.assertEqual(row["validation_status"], "Error")
        self.assertEqual(row["validation_error_code"], "RESYNC_PERIOD_CLOSED")
        posted.assert_not_called()

    def test_failed_repost_leaves_the_original_submitted(self):
        """Cancelling first and failing to repost would leave the period with neither
        entry — worse than the stale figure being corrected."""
        row = {"row_idx": 1, "validation_status": "Valid",
               "_resync_of": {"name": "ROW-OLD", "posted_doctype": "Journal Entry",
                              "posted_docname": "ACC-JV-TEST-0001", "row_idx": 7,
                              "parent": "RUN-OLD"}}
        run = frappe._dict(company=COMPANY, name="RUN-NEW")

        with patch("cashew_integration.importer.resync.frappe.db.exists",
                   return_value=True), \
             patch("cashew_integration.importer.resync.frappe.db.get_value",
                   return_value=(1, "2026-06-29")), \
             patch("cashew_integration.importer.resync._period_closed",
                   return_value=None), \
             patch("cashew_integration.importer.posting.post_row",
                   side_effect=Exception("boom")), \
             patch("cashew_integration.importer.resync.frappe.get_doc") as get_doc:
            doctype, _ = apply_resync(row, run)

        self.assertEqual(doctype, "")
        self.assertEqual(row["validation_error_code"], "RESYNC_REPOST_FAILED")
        get_doc.assert_not_called()

    def test_already_cancelled_original_posts_as_new_without_a_second_cancel(self):
        row = {"row_idx": 1, "validation_status": "Valid",
               "_resync_of": {"name": "ROW-OLD", "posted_doctype": "Journal Entry",
                              "posted_docname": "ACC-JV-TEST-0001", "row_idx": 7,
                              "parent": "RUN-OLD"}}
        run = frappe._dict(company=COMPANY, name="RUN-NEW")

        with patch("cashew_integration.importer.resync.frappe.db.exists",
                   return_value=True), \
             patch("cashew_integration.importer.resync.frappe.db.get_value",
                   return_value=(2, "2026-06-29")), \
             patch("cashew_integration.importer.posting.post_row",
                   return_value=("Journal Entry", "ACC-JV-TEST-0002")) as posted, \
             patch("cashew_integration.importer.resync.frappe.get_doc") as get_doc:
            doctype, docname = apply_resync(row, run)

        self.assertEqual((doctype, docname), ("Journal Entry", "ACC-JV-TEST-0002"))
        posted.assert_called_once()
        get_doc.assert_not_called()

    def test_open_period_cancels_the_original_and_stamps_both_rows(self):
        row = {"row_idx": 1, "validation_status": "Valid",
               "_resync_of": {"name": "ROW-OLD", "posted_doctype": "Journal Entry",
                              "posted_docname": "ACC-JV-TEST-0001", "row_idx": 7,
                              "parent": "RUN-OLD"}}
        run = frappe._dict(company=COMPANY, name="RUN-NEW")

        with patch("cashew_integration.importer.resync.frappe.db.exists",
                   return_value=True), \
             patch("cashew_integration.importer.resync.frappe.db.get_value",
                   return_value=(1, "2026-06-29")), \
             patch("cashew_integration.importer.resync._period_closed",
                   return_value=None), \
             patch("cashew_integration.importer.posting.post_row",
                   return_value=("Journal Entry", "ACC-JV-TEST-0002")), \
             patch("cashew_integration.importer.resync.frappe.get_doc") as get_doc, \
             patch("cashew_integration.importer.resync.frappe.db.set_value") as set_value:
            doctype, docname = apply_resync(row, run)

        self.assertEqual(docname, "ACC-JV-TEST-0002")
        get_doc.return_value.cancel.assert_called_once()
        self.assertEqual(row["revert_status"], RESYNCED)
        self.assertEqual(set_value.call_args[0][2]["revert_status"], SUPERSEDED)

    def test_the_cancel_is_flagged_as_ours(self):
        """Without the flag, reconcile.on_document_cancelled reports the app's own
        cancel as an external one."""
        seen = {}
        row = {"row_idx": 1, "validation_status": "Valid",
               "_resync_of": {"name": "ROW-OLD", "posted_doctype": "Journal Entry",
                              "posted_docname": "ACC-JV-TEST-0001", "row_idx": 7,
                              "parent": "RUN-OLD"}}
        run = frappe._dict(company=COMPANY, name="RUN-NEW")

        def _capture(*_args, **_kwargs):
            seen["flag"] = frappe.flags.get("cashew_reverting")
            return frappe._dict(cancel=lambda: None)

        with patch("cashew_integration.importer.resync.frappe.db.exists",
                   return_value=True), \
             patch("cashew_integration.importer.resync.frappe.db.get_value",
                   return_value=(1, "2026-06-29")), \
             patch("cashew_integration.importer.resync._period_closed",
                   return_value=None), \
             patch("cashew_integration.importer.posting.post_row",
                   return_value=("Journal Entry", "ACC-JV-TEST-0002")), \
             patch("cashew_integration.importer.resync.frappe.get_doc",
                   side_effect=_capture), \
             patch("cashew_integration.importer.resync.frappe.db.set_value"):
            apply_resync(row, run)

        self.assertEqual(seen.get("flag"), "RUN-NEW")
        self.assertIsNone(frappe.flags.get("cashew_reverting"), "flag must be cleared")


class TestStaleLoanMatcher(FrappeTestCase):
    """`correct_stale_loan_je` writes GL against a customer receivable, so its
    matcher is tested here rather than against a site — work.local no longer carries
    the import (73 Journal Entries, 3 import rows) and cannot exercise it."""

    def _row(self, **over):
        base = frappe._dict(
            name="ROW-1", parent="RUN-1", row_idx=7, raw_amount=150000.0,
            posted_doctype="Journal Entry", posted_docname="ACC-JV-TEST-0001",
            resolved_erp_account="Petty Cash - CS", resolved_party="HC",
            resolved_route="Loan Receivable JE",
        )
        base.update(over)
        return base

    def _find(self, rows, docstatus=1, company="Code.Solutions"):
        from cashew_integration.scripts import correct_stale_loan_je as mod

        with patch.object(mod.frappe, "get_all", return_value=rows), \
             patch.object(mod.frappe.db, "get_value",
                          side_effect=lambda dt, *a, **k:
                              company if dt == "Cashew Import Run" else docstatus):
            return mod._find(None)

    def test_matches_the_stale_loan(self):
        found = self._find([self._row()])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["journal_entry"], "ACC-JV-TEST-0001")

    def test_ignores_a_row_already_at_the_corrected_amount(self):
        self.assertEqual(self._find([self._row(raw_amount=148674.0)]), [])

    def test_ignores_a_different_account(self):
        self.assertEqual(self._find([self._row(resolved_erp_account="Saving - CS")]), [])

    def test_ignores_an_already_cancelled_document(self):
        self.assertEqual(self._find([self._row()], docstatus=2), [])

    def test_refuses_to_write_when_more_than_one_row_matches(self):
        from cashew_integration.scripts import correct_stale_loan_je as mod

        # `_find`'s own output shape, not the raw child rows it reads.
        two = [
            {"journal_entry": f"ACC-JV-TEST-000{n}", "txn_date": "2026-06-29",
             "account": "Petty Cash - CS", "raw_amount": 150000.0, "row_idx": n,
             "run": "RUN-1", "party": "HC", "row_name": f"ROW-{n}",
             "doctype": "Journal Entry", "company": "Code.Solutions"}
            for n in (1, 2)
        ]
        with patch.object(mod, "_find", return_value=two), \
             patch.object(mod, "_correct") as corrected:
            mod.run(apply=True)

        corrected.assert_not_called()


class TestIdempotencyStillSkipsUnchangedRows(FrappeTestCase):

    def test_resync_tagged_row_is_not_marked_duplicate(self):
        from cashew_integration.importer.idempotency import apply_idempotency_guard

        rows = [{"row_idx": 1, "source_pk": "pk-1", "source_hash": "new-hash",
                 "validation_status": "Valid"}]
        run = frappe._dict(company=COMPANY, name="RUN-NEW")

        with patch("cashew_integration.importer.idempotency.mark_changed_rows",
                   side_effect=lambda r, _run: r[0].update(
                       {"_resync_of": {"posted_docname": "ACC-JV-TEST-0001"}}) or 1), \
             patch("cashew_integration.importer.idempotency._fetch_posted_hashes",
                   return_value={"new-hash": ("Journal Entry", "ACC-JV-TEST-0001")}), \
             patch("cashew_integration.importer.idempotency._fetch_erp_document_hashes",
                   return_value={}):
            apply_idempotency_guard(rows, run)

        self.assertEqual(rows[0]["validation_status"], "Valid",
                         "an edited row must post, not skip as a duplicate")
