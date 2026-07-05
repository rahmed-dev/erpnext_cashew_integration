"""
f011 c003 — SQLite import GATE test suite (source_hash parity + posting/pairing).

This is the safety gate for "add alongside": it certifies that the SQLite reader
(f011 c001) is safe to run next to the CSV path. It has TWO independent halves —
a green Half 1 says NOTHING about Half 2:

  Half 1 — hash parity (DEDUP safety): the same transaction read via parse_csv
    and via read_sqlite produces an IDENTICAL source_hash, so the idempotency
    guard collapses a cross-source duplicate into ONE posting.

  Half 2 — posting/pairing (BOOKS safety): every internal Transfer JV balances,
    each posted pair maps to a real paired_transaction_fk, a dangling FK routes
    to External Transfer (not a broken internal JV), and a deleted master surfaces
    as an ERROR row rather than being silently dropped (the LEFT-JOIN contract —
    the very omission bug this feature fixes).

  >>> HASH PARITY GREEN != TRANSFERS POST CORRECTLY. <<<
  A reviewer reading a green Half 1 must not conclude the books are correct.

Residual gap (documented, out of scope here): the cross-source proof below is
SYNTHETIC — CSV and SQLite fixtures are built from one shared row list, so it
proves the two code paths converge on the same NORMALIZATION CONTRACT. It does
NOT prove read_sqlite matches Cashew's real CSV EXPORTER byte-for-byte; that
needs a CSV exported from the same Cashew DB state (spec c003 §"Ideal fixture",
still open). Close it when a matching real CSV export is available.

Run:  bench --site work.local run-tests --module cashew_integration.tests.test_sqlite_import
"""
import calendar
import csv
import io
import os
import sqlite3
import tempfile
from datetime import datetime, timezone

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt, get_system_timezone

from cashew_integration.importer.parser import parse_csv
from cashew_integration.importer.sqlite_reader import read_sqlite
from cashew_integration.importer.mapping import apply_mappings
from cashew_integration.importer.validation import validate_rows_at_queue_time
from cashew_integration.importer.worker import _process

# ── real data constants (mirror test_integration.py so mappings resolve) ─────────
COMPANY = "Code.Solutions"

ACCOUNT_MAPPINGS = [
    ("Petty Cash",  "Cash - CS",          "PKR"),
    ("NSave",       "Meezan Bank - CS",   "PKR"),
    ("Saving",      "Crypto - CS",        "PKR"),
    ("Investment",  "Earnest Money - CS", "PKR"),
    # External-partner account — used to resolve the dangling-FK External Transfer.
    ("PayPal",      "Meezan Bank - CS",   "PKR"),
]

# No category mappings needed: Half-1 categories are only HASHED (mapping runs
# after the hash and neither reader requires a mapping row to exist), and every
# Half-2 posting row is a transfer / external transfer, which skip category
# resolution entirely. Leaving this empty also avoids depending on category
# default-accounts that may not exist in this particular chart of accounts.
CATEGORY_MAPPINGS: list[tuple] = []

CSV_HEADER = [
    "account", "amount", "currency", "title", "note", "date", "income", "type",
    "category name", "subcategory name", "color", "icon", "emoji", "budget", "objective",
]

# ── shared logical transactions for Half 1 (parity) ──────────────────────────────
# Each row is emitted TWICE: once as a CSV cell (local-time string + UPPER currency,
# how Cashew's CSV exporter writes it) and once as a SQLite row (UTC epoch seconds +
# lowercase currency, how Cashew's DB stores it). The divergence is deliberate — it
# is what actually exercises the reader's .upper() / epoch→local-date / .strip()
# transforms. If both sides carried the same shape, those transforms would be untested.
#
# Ground-truth discipline (anti-trivial-pass): the CSV local-date STRING is a human
# literal; the SQLite epoch is derived from a UTC datetime literal via calendar.timegm
# (pure UTC, no tz library). Neither side is computed from the reader's own tz helper,
# so a bug in that helper cannot hide in the fixture. Karachi is UTC+5, no DST.
#
# fields: title (unique natural key), account (wallet name — may carry surrounding
# whitespace to test .strip()), currency (UPPER; DB gets .lower()), amount (signed
# float; income column drives direction, reader/parser both abs() for the hash),
# income ("true"/"false"), category, note, utc (naive UTC datetime → epoch),
# csv_local (local wall-clock string the CSV exporter would emit).
_SHARED = [
    dict(title="IncomeRow",    account="Petty Cash",   currency="PKR", amount=42000.0,
         income="true",  category="Freelance",         note="",
         utc=datetime(2025, 3, 1, 9, 0, 0),   csv_local="2025-03-01 14:00:00.000"),
    dict(title="ExpenseRow",   account="Petty Cash",   currency="PKR", amount=-2240.0,
         income="false", category="Entertainment",     note="",
         utc=datetime(2026, 4, 8, 9, 0, 0),   csv_local="2026-04-08 14:00:00.000"),
    dict(title="LowerCurRow",  account="NSave",        currency="PKR", amount=-500.0,
         income="false", category="Home",              note="",
         utc=datetime(2026, 5, 10, 9, 0, 0),  csv_local="2026-05-10 14:00:00.000"),
    # Highest-signal row: UTC calendar day (02-04) != Karachi-local day (02-05).
    dict(title="LateNightRow", account="Petty Cash",   currency="PKR", amount=-100.0,
         income="false", category="Bills & Fees",      note="",
         utc=datetime(2025, 2, 4, 22, 30, 0), csv_local="2025-02-05 03:30:00.000"),
    # >2 dp of significance — must hash on the 10dp form, not the 2dp raw_amount.
    dict(title="FullPrecRow",  account="Petty Cash",   currency="PKR", amount=-123.456789,
         income="false", category="Fuel",              note="",
         utc=datetime(2026, 1, 10, 6, 0, 0),  csv_local="2026-01-10 11:00:00.000"),
    # Surrounding whitespace on account/title/note — both readers must .strip() identically.
    dict(title="  TrailingRow  ", account="  Petty Cash  ", currency="PKR", amount=-7.0,
         income="false", category="Cursor",            note="hello world  ",
         utc=datetime(2026, 6, 6, 6, 0, 0),   csv_local="2026-06-06 11:00:00.000"),
    # Transfer leg — note carries an interior newline (kept, not stripped) + the → glyph.
    dict(title="TransferLeg",  account="Saving",       currency="PKR", amount=120000.0,
         income="true",  category="Balance Correction",
         note="Transferred Balance\nPetty Cash → Saving",
         utc=datetime(2026, 4, 8, 15, 27, 0), csv_local="2026-04-08 20:27:00.000"),
    dict(title="FxRow",        account="USD Wallet",   currency="USD", amount=-50.0,
         income="false", category="Cursor",            note="",
         utc=datetime(2026, 2, 2, 6, 0, 0),   csv_local="2026-02-02 11:00:00.000"),
]


def _epoch(dt: datetime) -> int:
    """Naive-UTC datetime → unix epoch seconds (pure UTC, no tz library)."""
    return calendar.timegm(dt.timetuple())


def _make_sqlite(wallets, categories, txns) -> bytes:
    """Build a minimal Cashew SQLite backup and return its bytes.

    Creates only the three tables read_sqlite's _READER_SQL touches. Written to a
    temp file (sqlite3 needs a path), then read back as bytes; read_sqlite opens
    those bytes mode=ro. *wallets*: (pk, name, currency). *categories*: (pk, name).
    *txns*: dicts with keys transaction_pk, name, amount, note, income, date_created,
    paired_transaction_fk, wallet_fk, category_fk, sub_category_fk, paid.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    try:
        conn = sqlite3.connect(tmp.name)
        try:
            conn.execute("CREATE TABLE wallets (wallet_pk INTEGER PRIMARY KEY, name TEXT, currency TEXT)")
            conn.execute("CREATE TABLE categories (category_pk INTEGER PRIMARY KEY, name TEXT)")
            conn.execute(
                "CREATE TABLE transactions ("
                "transaction_pk INTEGER PRIMARY KEY, name TEXT, amount REAL, note TEXT, "
                "income INTEGER, date_created INTEGER, paired_transaction_fk INTEGER, "
                "wallet_fk INTEGER, category_fk INTEGER, sub_category_fk INTEGER, paid INTEGER)"
            )
            conn.executemany("INSERT INTO wallets VALUES (?,?,?)", wallets)
            conn.executemany("INSERT INTO categories VALUES (?,?)", categories)
            conn.executemany(
                "INSERT INTO transactions (transaction_pk, name, amount, note, income, "
                "date_created, paired_transaction_fk, wallet_fk, category_fk, sub_category_fk, paid) "
                "VALUES (:transaction_pk,:name,:amount,:note,:income,:date_created,"
                ":paired_transaction_fk,:wallet_fk,:category_fk,:sub_category_fk,:paid)",
                txns,
            )
            conn.commit()
        finally:
            conn.close()
        with open(tmp.name, "rb") as fh:
            return fh.read()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


class TestSqliteImportGate(FrappeTestCase):

    # ── class setup: configure Cashew Settings + purge stale test docs ────────────

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # The reader converts epoch→site-local via get_system_timezone(). The Half-1
        # fixtures pin their local-date literals to Asia/Karachi (UTC+5). If the site
        # runs a different tz, those literals are wrong — skip loudly rather than pass
        # silently on a fixture that no longer means what it says.
        cls._sys_tz = get_system_timezone()
        if cls._sys_tz != "Asia/Karachi":
            import unittest
            raise unittest.SkipTest(
                f"Half-1 tz fixtures assume Asia/Karachi; site tz is {cls._sys_tz!r}."
            )

        settings = frappe.get_single("Cashew Settings")
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
        """Clean slate so the idempotency guard can't fire on re-run. Purges EVERY
        cashew-linked Journal Entry for the test company (not just those tied to a
        still-existing run — a JE orphaned by a prior deleted run would otherwise
        survive and skip this run's postings), then all runs + rows. Same disposable-
        test-data convention as test_integration, which likewise nukes all COMPANY runs
        (Code.Solutions holds no precious cashew data on work.local)."""
        for je in frappe.get_all(
            "Journal Entry",
            filters={"company": COMPANY, "cashew_import_run": ["is", "set"]},
            pluck="name",
        ):
            doc = frappe.get_doc("Journal Entry", je)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.db.delete("Journal Entry", {"name": je})
        for run_name in frappe.get_all(
            "Cashew Import Run", filters={"company": COMPANY}, pluck="name"
        ):
            frappe.db.delete("Cashew Import Row", {"parent": run_name})
            frappe.db.delete("Cashew Import Run", {"name": run_name})
        frappe.db.commit()

    def setUp(self):
        self._docs_to_cleanup = []

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

    def _create_run(self, rows):
        """Persist a Cashew Import Run with child rows, mirroring the PRODUCTION persist
        path (api._dict_to_child): copy every non-underscore key. Crucially this keeps
        income_flag (a real Cashew Import Row column) — the worker's canonical transfer
        direction rule (source=income false, dest=income true) reads it, so dropping it
        would make the JV direction fall back to row order and diverge from production.
        (test_integration's _create_run skips income_flag and its transfer test never
        asserts direction, so that gap went unnoticed there.)"""
        run = frappe.get_doc({
            "doctype":    "Cashew Import Run",
            "company":    COMPANY,
            "status":     "Queued",
            "rows_total": len(rows),
        })
        for row in rows:
            child = run.append("import_rows", {})
            for k, v in row.items():
                if k.startswith("_"):
                    continue
                try:
                    child.set(k, v)
                except Exception:
                    pass
        run.insert(ignore_permissions=True, ignore_mandatory=True)
        frappe.db.commit()
        self._track("Cashew Import Run", run.name)
        return run

    # ── Half 1 fixture builders ───────────────────────────────────────────────────

    @staticmethod
    def _build_csv() -> bytes:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(CSV_HEADER)
        for t in _SHARED:
            w.writerow([
                t["account"], t["amount"], t["currency"], t["title"], t["note"],
                t["csv_local"], t["income"], "null", t["category"], "",
                "", "", "", "", "",
            ])
        return buf.getvalue().encode("utf-8")

    @staticmethod
    def _build_sqlite() -> bytes:
        # One wallet per unique (account, currency); currency stored lowercase (as Cashew does).
        wallets, wpk = [], {}
        cats, cpk = [], {}
        for t in _SHARED:
            wkey = (t["account"], t["currency"])
            if wkey not in wpk:
                wpk[wkey] = len(wpk) + 1
                wallets.append((wpk[wkey], t["account"], t["currency"].lower()))
            if t["category"] not in cpk:
                cpk[t["category"]] = len(cpk) + 1
                cats.append((cpk[t["category"]], t["category"]))
        txns = []
        for i, t in enumerate(_SHARED, start=1):
            txns.append(dict(
                transaction_pk=i, name=t["title"], amount=t["amount"], note=t["note"],
                income=1 if t["income"] == "true" else 0, date_created=_epoch(t["utc"]),
                paired_transaction_fk=None, wallet_fk=wpk[(t["account"], t["currency"])],
                category_fk=cpk[t["category"]], sub_category_fk=None, paid=1,
            ))
        return _make_sqlite(wallets, cats, txns)

    # ── Half 1: golden cross-source hash parity ───────────────────────────────────

    def test_half1_source_hash_parity_across_csv_and_sqlite(self):
        """Same txn via parse_csv and via read_sqlite → identical source_hash.
        This is DEDUP safety only (see module docstring): it does NOT certify posting."""
        csv_rows = parse_csv(self._build_csv(), "PKR")
        sql_rows = read_sqlite(self._build_sqlite(), "PKR")

        by_title_csv = {r["title"]: r for r in csv_rows}
        by_title_sql = {r["title"]: r for r in sql_rows}

        # Titles are stripped identically by both readers — match on the stripped key.
        expected = {t["title"].strip() for t in _SHARED}
        self.assertEqual(set(by_title_csv), expected, "CSV titles mismatch.")
        self.assertEqual(set(by_title_sql), expected, "SQLite titles mismatch.")

        for title in expected:
            c = by_title_csv[title]
            s = by_title_sql[title]
            self.assertIsNotNone(c.get("source_hash"), f"{title}: CSV hash missing.")
            self.assertEqual(
                c["source_hash"], s["source_hash"],
                f"{title}: source_hash diverged (CSV vs SQLite) — dedup would double-post.",
            )

    def test_half1_late_night_row_crosses_local_day_boundary(self):
        """The tz trap, isolated: the late-night row's UTC calendar day differs from
        its Karachi-local day. If the reader failed to convert tz, only this row would
        diverge — hence the single highest-signal parity assertion."""
        t = next(x for x in _SHARED if x["title"] == "LateNightRow")
        utc_day = datetime.fromtimestamp(_epoch(t["utc"]), tz=timezone.utc).date().isoformat()
        self.assertEqual(utc_day, "2025-02-04", "Fixture must straddle midnight in UTC.")
        self.assertEqual(t["csv_local"][:10], "2025-02-05", "CSV local date must be the next day.")

        sql_rows = read_sqlite(self._build_sqlite(), "PKR")
        row = next(r for r in sql_rows if r["title"] == "LateNightRow")
        self.assertEqual(
            row["txn_date"], "2025-02-05",
            "Reader must land the late-night UTC txn on the next Karachi-local day.",
        )

    def test_half1_full_precision_amount_hashes_on_10dp(self):
        """A >2dp amount hashes on the 10dp form, not the 2dp raw_amount — proven by
        parity holding for the FullPrecRow (raw_amount is rounded to 2dp for display)."""
        sql_rows = read_sqlite(self._build_sqlite(), "PKR")
        row = next(r for r in sql_rows if r["title"] == "FullPrecRow")
        self.assertEqual(row["raw_amount"], 123.46, "raw_amount is the 2dp display value.")
        # parity for this title is asserted in the main Half-1 test; here we pin that
        # the 2dp rounding did NOT leak into the hash by confirming the CSV twin matches.
        csv_rows = parse_csv(self._build_csv(), "PKR")
        crow = next(r for r in csv_rows if r["title"] == "FullPrecRow")
        self.assertEqual(row["source_hash"], crow["source_hash"])

    # ── Half 2 fixture: internal pair + dangling-FK external + deleted master ──────

    @staticmethod
    def _build_posting_sqlite() -> bytes:
        wallets = [
            (1, "Petty Cash", "pkr"),
            (2, "Saving",     "pkr"),
        ]
        cats = [(1, "Balance Correction")]
        note_saving = "Transferred Balance\nPetty Cash → Saving"
        note_paypal = "Transferred Balance\nPetty Cash → PayPal"
        base_utc = _epoch(datetime(2026, 4, 8, 10, 0, 0))
        txns = [
            # internal transfer pair — FK-linked (pk1 <-> pk2), PKR same-currency
            dict(transaction_pk=1, name="XferSavingIn", amount=120000.0, note=note_saving,
                 income=1, date_created=base_utc, paired_transaction_fk=2,
                 wallet_fk=2, category_fk=1, sub_category_fk=None, paid=1),
            dict(transaction_pk=2, name="XferPettyOut", amount=-120000.0, note=note_saving,
                 income=0, date_created=base_utc, paired_transaction_fk=1,
                 wallet_fk=1, category_fk=1, sub_category_fk=None, paid=1),
            # dangling FK (999 not present) → External Transfer (partner PayPal, mapped)
            dict(transaction_pk=3, name="XferExternal", amount=-5000.0, note=note_paypal,
                 income=0, date_created=base_utc, paired_transaction_fk=999,
                 wallet_fk=1, category_fk=1, sub_category_fk=None, paid=1),
            # deleted master: wallet_fk 888 absent → LEFT JOIN NULL → SQL_MASTER_UNRESOLVED
            dict(transaction_pk=4, name="DeletedWallet", amount=-100.0, note="",
                 income=0, date_created=base_utc, paired_transaction_fk=None,
                 wallet_fk=888, category_fk=1, sub_category_fk=None, paid=1),
        ]
        return _make_sqlite(wallets, cats, txns)

    def test_half2_deleted_master_becomes_error_row_not_dropped(self):
        """LEFT-JOIN contract: a txn whose wallet was deleted appears as an ERROR row
        (SQL_MASTER_UNRESOLVED), never silently dropped — that silent drop is the
        omission bug this whole feature exists to fix."""
        rows = read_sqlite(self._build_posting_sqlite(), "PKR")
        # All four txns present (nothing dropped by the LEFT JOIN).
        self.assertEqual(len(rows), 4, "All 4 txns must survive the LEFT JOIN.")
        err = next(r for r in rows if r["title"] == "DeletedWallet")
        self.assertEqual(err["validation_status"], "Error")
        self.assertEqual(err["validation_error_code"], "SQL_MASTER_UNRESOLVED")

    def test_half2_fk_pairing_is_authoritative(self):
        """FK-driven pairing (c001 §5.5): the two internal legs point at each other by
        row_idx, and that pairing traces to a real paired_transaction_fk link — not the
        note+time heuristic. Verified on the reader output before persistence."""
        rows = read_sqlite(self._build_posting_sqlite(), "PKR")
        by_pk = {r["_txn_pk"]: r for r in rows}
        leg_in, leg_out = by_pk[1], by_pk[2]
        for leg in (leg_in, leg_out):
            self.assertEqual(leg["txn_type"], "Transfer")
            self.assertEqual(leg["resolved_route"], "Transfer JV")
        # each leg's transfer_pair_row_idx == the OTHER leg's row_idx …
        self.assertEqual(leg_in["transfer_pair_row_idx"], leg_out["row_idx"])
        self.assertEqual(leg_out["transfer_pair_row_idx"], leg_in["row_idx"])
        # … and that pairing corresponds to the DB FK (pk1<->pk2), not a note guess.
        self.assertEqual(leg_in["_paired_fk"], leg_out["_txn_pk"])
        self.assertEqual(leg_out["_paired_fk"], leg_in["_txn_pk"])

    def test_half2_dangling_fk_routes_to_external_transfer(self):
        """A transfer whose partner FK is dangling (partner deleted / out of window)
        routes to External Transfer JE — never a half-built internal JV."""
        rows = read_sqlite(self._build_posting_sqlite(), "PKR")
        ext = next(r for r in rows if r["title"] == "XferExternal")
        self.assertEqual(ext["txn_type"], "External Transfer")
        self.assertEqual(ext["resolved_route"], "External Transfer JE")
        self.assertIsNone(ext["transfer_pair_row_idx"])

    def test_half2_transfer_jv_posts_balanced_and_maps_to_fk(self):
        """End-to-end through the production pipeline: the internal pair posts ONE
        submitted Journal Entry whose debits == credits, and both legs reference it.
        This is the BOOKS-safety half — independent of Half-1 hash parity."""
        rows = read_sqlite(self._build_posting_sqlite(), "PKR")
        run_ctx = frappe.get_doc({"doctype": "Cashew Import Run", "company": COMPANY})
        run_ctx.company_currency = "PKR"
        apply_mappings(rows, run_ctx)
        validate_rows_at_queue_time(rows)

        valid = [r for r in rows if r.get("validation_status") == "Valid"]
        # transfer pair (2) + external (1); the deleted-master row is Error, excluded.
        self.assertEqual(len(valid), 3, "Expected 2 transfer legs + 1 external, all Valid.")

        run = self._create_run(valid)
        _process(run.name)
        run.reload()

        # Track every posted JE FIRST, before any assertion — so a mid-test failure
        # still cleans up via tearDown and doesn't orphan a JE that skips the next run.
        for child in run.import_rows:
            if child.posted_doctype == "Journal Entry" and child.posted_docname:
                self._track("Journal Entry", child.posted_docname)

        self.assertEqual(run.status, "Completed", f"Run status: {run.status}.")
        self.assertEqual(run.rows_failed, 0, f"{run.rows_failed} row(s) failed.")
        # Guard against a dirty-state false-green: an idempotency-Skipped row still
        # carries posted_docname (pointing at the ORIGINAL doc), so the account/amount
        # assertions below could pass without anything posting THIS run. Requiring zero
        # skips proves every posted_docname reflects a real posting from this run.
        # (rows_posted itself counts a transfer PAIR as one posting, so it's not a clean
        # per-row check here.)
        self.assertEqual(run.rows_skipped, 0, f"{run.rows_skipped} row(s) unexpectedly Skipped.")

        # Transfer legs share exactly one JE; external posts its own.
        transfer_children = [c for c in run.import_rows if c.txn_type == "Transfer"]
        jv_names = {c.posted_docname for c in transfer_children if c.posted_docname}
        self.assertEqual(len(jv_names), 1, "Both transfer legs must reference ONE JV.")
        jv_name = next(iter(jv_names))
        self._track("Journal Entry", jv_name)

        jv = frappe.get_doc("Journal Entry", jv_name)
        self.assertEqual(jv.docstatus, 1, "Transfer JV must be submitted.")

        # A submitted JE is balanced BY CONSTRUCTION (ERPNext enforces debit==credit at
        # submit) — so "it balanced" proves nothing. The gate must prove the money moved
        # between the RIGHT accounts, in the RIGHT amount, in the RIGHT direction — that is
        # exactly the wrong-account / wrong-amount failure class the CSV path allegedly had.
        # Cashew note "Petty Cash → Saving": Saving's ERP (Crypto - CS) receives (debit),
        # Petty Cash's ERP (Cash - CS) is drawn down (credit); 120000 PKR, 1:1.
        lines = {a.account: a for a in jv.accounts}
        self.assertEqual(
            set(lines), {"Cash - CS", "Crypto - CS"},
            "JV must move between the two wallets' MAPPED ERP accounts, not others.",
        )
        self.assertAlmostEqual(flt(lines["Crypto - CS"].debit),  120000.0, places=2)
        self.assertAlmostEqual(flt(lines["Crypto - CS"].credit),      0.0, places=2)
        self.assertAlmostEqual(flt(lines["Cash - CS"].credit),   120000.0, places=2)
        self.assertAlmostEqual(flt(lines["Cash - CS"].debit),         0.0, places=2)

        # External Transfer leg posts a submitted JE between Petty Cash's ERP (Cash - CS)
        # and the partner PayPal's mapped ERP (Meezan Bank - CS), for 5000 PKR.
        ext_children = [c for c in run.import_rows if c.txn_type == "External Transfer"]
        self.assertEqual(len(ext_children), 1)
        ext_je = ext_children[0].posted_docname
        self.assertTrue(ext_je, "External Transfer must post a JE.")
        self._track("Journal Entry", ext_je)
        ext = frappe.get_doc("Journal Entry", ext_je)
        self.assertEqual(ext.docstatus, 1)
        self.assertEqual(
            {a.account for a in ext.accounts}, {"Cash - CS", "Meezan Bank - CS"},
            "External JE must move between the wallet's ERP and the partner's mapped ERP.",
        )
        self.assertAlmostEqual(
            max(flt(a.debit) for a in ext.accounts), 5000.0, places=2,
            msg="External JE must move the transaction amount (5000 PKR).",
        )

    # ── Half 2: date-window boundary (site-local, same tz logic as Half 1) ────────

    def test_half2_date_window_boundary_is_site_local(self):
        """read_sqlite(from_date, to_date) filters on the SITE-LOCAL date. The late-night
        row (UTC 2025-02-04 → local 2025-02-05) must be INSIDE a 2025-02-05 window and
        OUTSIDE a 2025-02-04 window — the boundary lands on the local side, not UTC."""
        late_utc = _epoch(datetime(2025, 2, 4, 22, 30, 0))  # → Karachi 2025-02-05 03:30
        wallets = [(1, "Petty Cash", "pkr")]
        cats = [(1, "Fuel")]
        txn = dict(transaction_pk=1, name="Boundary", amount=-1.0, note="",
                   income=0, date_created=late_utc, paired_transaction_fk=None,
                   wallet_fk=1, category_fk=1, sub_category_fk=None, paid=1)
        content = _make_sqlite(wallets, cats, [txn])

        inside = read_sqlite(content, "PKR", from_date="2025-02-05", to_date="2025-02-05")
        self.assertEqual(len(inside), 1, "Local-date row must be inside the local-day window.")
        self.assertEqual(inside[0]["txn_date"], "2025-02-05")

        outside = read_sqlite(content, "PKR", from_date="2025-02-04", to_date="2025-02-04")
        self.assertEqual(len(outside), 0, "Row must fall OUTSIDE the UTC-day window (local != UTC).")

    def test_half2_from_after_to_raises(self):
        """A from_date later than to_date is a clean, titled error — not a stack trace."""
        content = self._build_posting_sqlite()
        with self.assertRaises(frappe.ValidationError):
            read_sqlite(content, "PKR", from_date="2025-03-01", to_date="2025-02-01")
