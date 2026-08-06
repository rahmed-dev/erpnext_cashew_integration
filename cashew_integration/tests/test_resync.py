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
    SUPERSEDE_FAILED,
    SUPERSEDED,
    apply_supersessions,
    mark_changed_rows,
    screen_resyncs,
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


def _tagged(row_idx=1, **over):
    """A row carrying a resync tag, in the shape mark_changed_rows produces."""
    row = {"row_idx": row_idx, "validation_status": "Valid",
           "_resync_of": {"name": "ROW-OLD", "posted_doctype": "Journal Entry",
                          "posted_docname": "ACC-JV-TEST-0001", "row_idx": 7,
                          "parent": "RUN-OLD"}}
    row.update(over)
    return row


RUN = frappe._dict(company=COMPANY, name="RUN-NEW")


class TestScreenResyncs(FrappeTestCase):
    """Screening runs before the posting loop. A row that cannot legally supersede
    must be refused while refusing is still free — once the replacement is posted,
    declining to cancel the original means two live entries."""

    def test_closed_period_errors_the_row(self):
        row = _tagged()

        with patch("cashew_integration.importer.resync.frappe.db.exists",
                   return_value=True), \
             patch("cashew_integration.importer.resync.frappe.db.get_value",
                   return_value=(1, "2026-06-29")), \
             patch("cashew_integration.importer.resync._period_closed",
                   return_value="disabled Fiscal Year 2026"):
            screen_resyncs([row], RUN)

        self.assertEqual(row["validation_status"], "Error")
        self.assertEqual(row["validation_error_code"], "RESYNC_PERIOD_CLOSED")
        self.assertNotIn("_resync_of", row)

    def test_closed_period_errors_both_legs_of_a_transfer_pair(self):
        """Erroring one leg alone leaves the other to fail as TRANSFER_PAIR_INCOMPLETE,
        which names a symptom instead of the cause."""
        src = _tagged(1, txn_type="Transfer", transfer_pair_row_idx=2)
        dst = _tagged(2, txn_type="Transfer", transfer_pair_row_idx=1)

        with patch("cashew_integration.importer.resync.frappe.db.exists",
                   return_value=True), \
             patch("cashew_integration.importer.resync.frappe.db.get_value",
                   return_value=(1, "2026-06-29")), \
             patch("cashew_integration.importer.resync._period_closed",
                   return_value="disabled Fiscal Year 2026"):
            screen_resyncs([src, dst], RUN)

        for leg in (src, dst):
            self.assertEqual(leg["validation_error_code"], "RESYNC_PERIOD_CLOSED")
            self.assertNotIn("_resync_of", leg)

    def test_already_cancelled_original_drops_the_tag(self):
        """It posts as an ordinary new row — and must not be counted or logged as a
        resync it never performed."""
        row = _tagged()

        with patch("cashew_integration.importer.resync.frappe.db.exists",
                   return_value=True), \
             patch("cashew_integration.importer.resync.frappe.db.get_value",
                   return_value=(2, "2026-06-29")):
            screen_resyncs([row], RUN)

        self.assertNotIn("_resync_of", row)
        self.assertEqual(row["validation_status"], "Valid")

    def test_missing_original_drops_the_tag(self):
        row = _tagged()
        with patch("cashew_integration.importer.resync.frappe.db.exists",
                   return_value=False):
            screen_resyncs([row], RUN)
        self.assertNotIn("_resync_of", row)


class TestApplySupersessions(FrappeTestCase):
    """Cancellation happens only after the whole run has posted, so the replacement
    provably exists before anything is cancelled."""

    def test_cancels_the_original_and_records_lineage_both_ways(self):
        row = _tagged(posted_doctype="Journal Entry",
                      posted_docname="ACC-JV-TEST-0002")

        with patch("cashew_integration.importer.resync.frappe.get_doc") as get_doc, \
             patch("cashew_integration.importer.resync.frappe.db.set_value") as set_value:
            superseded, failed = apply_supersessions([row], RUN)

        self.assertEqual((superseded, failed), (1, 0))
        get_doc.return_value.cancel.assert_called_once()
        self.assertEqual(row["revert_status"], RESYNCED)
        self.assertEqual(row["supersedes"], "ACC-JV-TEST-0001")
        patch_written = set_value.call_args[0][2]
        self.assertEqual(patch_written["revert_status"], SUPERSEDED)
        self.assertEqual(patch_written["superseded_by"], "ACC-JV-TEST-0002")

    def test_a_row_that_never_posted_is_not_superseded(self):
        """A refused or failed row leaves the original in place — the ledger keeps the
        stale figure, which is recoverable; cancelling would lose the entry entirely."""
        row = _tagged()  # no posted_docname

        with patch("cashew_integration.importer.resync.frappe.get_doc") as get_doc:
            superseded, failed = apply_supersessions([row], RUN)

        self.assertEqual((superseded, failed), (0, 0))
        get_doc.assert_not_called()

    def test_a_transfer_pair_cancels_its_shared_document_once(self):
        prior = {"name": "ROW-OLD", "posted_doctype": "Journal Entry",
                 "posted_docname": "ACC-JV-TEST-0001", "row_idx": 7,
                 "parent": "RUN-OLD"}
        legs = [
            {"row_idx": 1, "_resync_of": prior, "posted_doctype": "Journal Entry",
             "posted_docname": "ACC-JV-TEST-0002"},
            {"row_idx": 2, "_resync_of": prior, "posted_doctype": "Journal Entry",
             "posted_docname": "ACC-JV-TEST-0002"},
        ]

        with patch("cashew_integration.importer.resync.frappe.get_doc") as get_doc, \
             patch("cashew_integration.importer.resync.frappe.db.set_value"):
            superseded, failed = apply_supersessions(legs, RUN)

        self.assertEqual((superseded, failed), (1, 0),
                         "one shared JE, cancelled once")
        get_doc.return_value.cancel.assert_called_once()
        for leg in legs:
            self.assertEqual(leg["revert_status"], RESYNCED)
            self.assertEqual(leg["supersedes"], "ACC-JV-TEST-0001")

    def test_a_failed_cancel_is_counted_failed_and_says_both_are_live(self):
        """This is the one outcome that puts two live documents in the ledger for a
        single transaction. It must fail the run, never pass quietly."""
        row = _tagged(posted_doctype="Journal Entry",
                      posted_docname="ACC-JV-TEST-0002")

        with patch("cashew_integration.importer.resync.frappe.get_doc",
                   side_effect=Exception("locked")), \
             patch("cashew_integration.importer.resync.frappe.log_error"), \
             patch("cashew_integration.importer.resync.frappe.get_traceback",
                   return_value="tb"):
            superseded, failed = apply_supersessions([row], RUN)

        self.assertEqual((superseded, failed), (0, 1))
        self.assertEqual(row["revert_status"], SUPERSEDE_FAILED)
        self.assertIn("BOTH are now live", row["revert_error"])

    def test_the_cancel_is_flagged_as_ours(self):
        """Without the flag, reconcile.on_document_cancelled reports the app's own
        cancel as an external one."""
        seen = {}
        row = _tagged(posted_doctype="Journal Entry",
                      posted_docname="ACC-JV-TEST-0002")

        def _capture(*_args, **_kwargs):
            seen["flag"] = frappe.flags.get("cashew_reverting")
            return frappe._dict(cancel=lambda: None)

        with patch("cashew_integration.importer.resync.frappe.get_doc",
                   side_effect=_capture), \
             patch("cashew_integration.importer.resync.frappe.db.set_value"):
            apply_supersessions([row], RUN)

        self.assertEqual(seen.get("flag"), "RUN-NEW")
        self.assertIsNone(frappe.flags.get("cashew_reverting"), "flag must be cleared")


class TestTransferPairTagging(FrappeTestCase):
    """A transfer's two legs share one Journal Entry but hash separately."""

    def test_editing_one_leg_tags_both(self):
        """Otherwise the unedited leg is skipped as a duplicate, the tagged leg is
        orphaned as TRANSFER_PAIR_INCOMPLETE, and the stale JV stays submitted."""
        rows = [
            {"row_idx": 1, "source_pk": "pk-1", "source_hash": "new-hash",
             "validation_status": "Valid", "txn_type": "Transfer",
             "transfer_pair_row_idx": 2},
            {"row_idx": 2, "source_pk": "pk-2", "source_hash": "unchanged",
             "validation_status": "Valid", "txn_type": "Transfer",
             "transfer_pair_row_idx": 1},
        ]
        prior = [
            {"name": "ROW-A", "source_pk": "pk-1", "source_hash": "old-hash",
             "row_idx": 7, "posted_doctype": "Journal Entry",
             "posted_docname": "ACC-JV-TEST-0001", "parent": "RUN-OLD"},
            {"name": "ROW-B", "source_pk": "pk-2", "source_hash": "unchanged",
             "row_idx": 8, "posted_doctype": "Journal Entry",
             "posted_docname": "ACC-JV-TEST-0001", "parent": "RUN-OLD"},
        ]

        with patch("cashew_integration.importer.resync.frappe.db.sql",
                   return_value=prior):
            tagged = mark_changed_rows(rows, RUN)

        self.assertEqual(tagged, 2)
        self.assertEqual(rows[1]["_resync_of"]["name"], "ROW-B",
                         "the partner keeps its own prior row when it has one")


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


class TestWindowReasonGate(FrappeTestCase):
    """An import window may only CREATE entries dated inside it.

    Widening the reader to created-OR-modified means it now returns transactions dated
    before the window that were merely edited inside it. One with a prior posting is a
    revision to apply; one without is a transaction the operator never asked to import,
    and posting it backdates a new entry into an earlier period.
    """

    def test_reader_labels_why_the_row_survived_the_window(self):
        edited_only = read_sqlite(
            _build_sqlite(148674.0, MODIFIED), "PKR",
            from_date="2026-07-01", to_date="2026-07-31",
        )[0]
        created_in = read_sqlite(
            _build_sqlite(148674.0, MODIFIED), "PKR",
            from_date="2026-06-01", to_date="2026-06-30",
        )[0]

        self.assertEqual(edited_only["_window_reason"], "modified")
        self.assertEqual(created_in["_window_reason"], "created")
        self.assertNotIn(
            "_window_reason", {k: 1 for k in edited_only if not k.startswith("_")},
            "private key — never persisted to the child table",
        )

    def test_no_window_at_all_is_always_created(self):
        rows = read_sqlite(_build_sqlite(148674.0, MODIFIED), "PKR")
        self.assertEqual(rows[0]["_window_reason"], "created")

    def test_edited_row_with_no_prior_posting_is_skipped_not_posted(self):
        from cashew_integration.importer.idempotency import apply_idempotency_guard

        rows = [{"row_idx": 1, "source_pk": "pk-9", "source_hash": "h",
                 "txn_date": "2025-11-02", "source_modified": "2026-08-05 10:00:00",
                 "validation_status": "Valid", "_window_reason": "modified"}]

        with patch("cashew_integration.importer.idempotency.mark_changed_rows",
                   return_value=0), \
             patch("cashew_integration.importer.idempotency._fetch_posted_hashes",
                   return_value={}), \
             patch("cashew_integration.importer.idempotency._fetch_erp_document_hashes",
                   return_value={}):
            apply_idempotency_guard(rows, RUN)

        self.assertEqual(rows[0]["validation_status"], "Skipped")
        self.assertIn("Widen the window", rows[0]["validation_error_message"])

    def test_edited_row_with_a_prior_posting_still_resyncs(self):
        from cashew_integration.importer.idempotency import apply_idempotency_guard

        rows = [{"row_idx": 1, "source_pk": "pk-1", "source_hash": "new-hash",
                 "txn_date": "2026-06-29", "validation_status": "Valid",
                 "_window_reason": "modified"}]

        with patch("cashew_integration.importer.idempotency.mark_changed_rows",
                   side_effect=lambda r, _run: r[0].update(
                       {"_resync_of": {"posted_docname": "ACC-JV-TEST-0001"}}) or 1), \
             patch("cashew_integration.importer.idempotency._fetch_posted_hashes",
                   return_value={}), \
             patch("cashew_integration.importer.idempotency._fetch_erp_document_hashes",
                   return_value={}):
            apply_idempotency_guard(rows, RUN)

        self.assertEqual(rows[0]["validation_status"], "Valid",
                         "the loan case: out-of-window, but a revision of a posting")


class TestReconcileTreatsSupersessionAsLineage(FrappeTestCase):
    """A superseded document is cancelled by design. Reported as drift it would make
    every run that ever resynced permanently unclean, and the real signal would drown."""

    def _report(self, row, successor_docstatus=1, successor_exists=True):
        from cashew_integration.importer import reconcile as mod

        with patch.object(mod.frappe, "get_doc",
                          return_value=frappe._dict(status="Completed", get=lambda *_: 0)), \
             patch.object(mod.frappe, "get_all",
                          side_effect=[[frappe._dict(row)], []]), \
             patch.object(mod.frappe.db, "exists",
                          side_effect=lambda _dt, name: (
                              successor_exists if name == "ACC-JV-TEST-0002" else True)), \
             patch.object(mod.frappe.db, "get_value",
                          side_effect=lambda _dt, name, fields: (
                              successor_docstatus if fields == "docstatus"
                              else (2, "2026-06-29"))):
            return mod.reconcile_run("RUN-OLD")

    def _row(self, **over):
        base = {"name": "ROW-OLD", "row_idx": 7, "txn_date": "2026-06-29",
                "raw_amount": 150000.0, "base_amount": 150000.0,
                "posted_doctype": "Journal Entry",
                "posted_docname": "ACC-JV-TEST-0001",
                "validation_status": "Valid", "revert_status": SUPERSEDED,
                "superseded_by": "ACC-JV-TEST-0002", "txn_type": "Loan Receivable"}
        base.update(over)
        return base

    def test_a_live_successor_is_not_an_issue(self):
        report = self._report(self._row())
        self.assertEqual(report["issues"], [])

    def test_a_vanished_successor_is_reported(self):
        report = self._report(self._row(), successor_exists=False)
        self.assertEqual(report["issues"][0]["problem"], "supersession-broken")

    def test_a_cancelled_successor_is_reported(self):
        report = self._report(self._row(), successor_docstatus=2)
        self.assertEqual(report["issues"][0]["problem"], "supersession-broken")

    def test_an_ordinary_external_cancel_is_still_drift(self):
        report = self._report(self._row(revert_status=None, superseded_by=None))
        self.assertEqual(report["issues"][0]["problem"], "cancelled")


class TestPostingPathDoesNotOwnRevertState(FrappeTestCase):
    """revert_status belongs to reconcile.py and process_revert. The posting path may
    only add to it — writing it unconditionally erased stamps it did not make."""

    def test_write_row_result_does_not_blank_an_existing_stamp(self):
        from cashew_integration.importer import worker as mod

        # The shape _row_to_dict produces: every field present, most of them None.
        row = {"row_idx": 1, "validation_status": "Valid", "revert_status": None,
               "revert_error": None, "supersedes": None, "superseded_by": None}
        run = frappe._dict(name="RUN-NEW")

        with patch.object(mod.frappe.db, "set_value") as set_value, \
             patch.object(mod, "emit_row_update"):
            mod._write_row_result(run, row)

        self.assertNotIn("revert_status", set_value.call_args[0][2])
        self.assertNotIn("revert_error", set_value.call_args[0][2])

    def test_write_row_result_persists_a_resync_stamp(self):
        from cashew_integration.importer import worker as mod

        row = {"row_idx": 1, "validation_status": "Valid",
               "revert_status": RESYNCED, "supersedes": "ACC-JV-TEST-0001"}
        run = frappe._dict(name="RUN-NEW")

        with patch.object(mod.frappe.db, "set_value") as set_value, \
             patch.object(mod, "emit_row_update"):
            mod._write_row_result(run, row)

        written = set_value.call_args[0][2]
        self.assertEqual(written["revert_status"], RESYNCED)
        self.assertEqual(written["supersedes"], "ACC-JV-TEST-0001")
