"""
Tests for the Cashew Budget import (f012 c012).

Two halves, deliberately separated:

* ``read_budgets`` is exercised against a synthetic SQLite backup built to the
  SAME column shape as the real 2026-08-07 export, including the four traps that
  decision C5.1–C5.5 record: the wallet scope lives in ``wallet_fks`` (not the
  scalar ``wallet_fk``), PKs are opaque strings that are not always UUIDs, dates
  are epoch seconds in the SITE timezone, and ``archived`` — not ``end_date`` —
  is the inactive signal.
* ``resolve_scope`` is exercised with plain dicts, so the mapping gate can be
  tested without touching the Cashew Settings singleton.

Run:  bench --site work.local run-tests --module cashew_integration.tests.test_budgets
"""

import json
import os
import sqlite3
import tempfile

import frappe
from frappe.tests.utils import FrappeTestCase

from cashew_integration.importer.budgets import resolve_scope
from cashew_integration.importer.sqlite_reader import read_budgets

# 2025-08-01 00:00:00 +05:00 — the anchor both live budgets carry.
ANCHOR_EPOCH = 1753988400
# 2025-08-31, an end_date well before "now": present on both live budgets, and
# both are still active. Nothing may read activity from it.
END_EPOCH = 1756642369

_SCHEMA = """
CREATE TABLE wallets (wallet_pk TEXT PRIMARY KEY, name TEXT, currency TEXT);
CREATE TABLE categories (
    category_pk TEXT PRIMARY KEY, name TEXT, income INTEGER,
    main_category_pk TEXT
);
CREATE TABLE budgets (
    budget_pk TEXT PRIMARY KEY, name TEXT, amount REAL, start_date INTEGER,
    end_date INTEGER, wallet_fks TEXT, category_fks TEXT,
    category_fks_exclude TEXT, income INTEGER, archived INTEGER,
    period_length INTEGER, reoccurrence INTEGER, pinned INTEGER,
    "order" INTEGER, wallet_fk TEXT, budget_transaction_filters TEXT
);
"""


def _build_sqlite(budget_overrides: dict | None = None) -> bytes:
    """A backup with two wallets, three categories (one a sub-category), one budget."""
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    conn = sqlite3.connect(tmp.name)
    conn.executescript(_SCHEMA)
    conn.executemany(
        "INSERT INTO wallets VALUES (?,?,?)",
        [("w-uuid", "Saving", "pkr"), ("0", "Investment", "pkr")],
    )
    conn.executemany(
        "INSERT INTO categories VALUES (?,?,?,?)",
        [
            # "5" is a seeded integer-string PK in the real export, not a UUID.
            ("5", "Entertainment", 0, None),
            ("c-uuid", "Food", 0, None),
            ("s-uuid", "Coffee", 0, "c-uuid"),
        ],
    )
    budget = {
        "budget_pk": "b-uuid",
        "name": "Food outdoor",
        "amount": 10000.0,
        "start_date": ANCHOR_EPOCH,
        "end_date": END_EPOCH,
        "wallet_fks": None,
        "category_fks": json.dumps(["5"]),
        "category_fks_exclude": "[]",
        "income": 0,
        "archived": 0,
        "period_length": 1,
        "reoccurrence": 3,
        "pinned": 1,
        "order": 0,
        # The display anchor. Reading THIS as the scope is the C5.1 trap.
        "wallet_fk": "0",
        "budget_transaction_filters": "[5]",
    }
    budget.update(budget_overrides or {})
    conn.execute(
        "INSERT INTO budgets ({}) VALUES ({})".format(
            ", ".join(f'"{k}"' for k in budget), ", ".join("?" * len(budget))
        ),
        list(budget.values()),
    )
    conn.commit()
    conn.close()
    with open(tmp.name, "rb") as fh:
        content = fh.read()
    os.unlink(tmp.name)
    return content


class TestReadBudgets(FrappeTestCase):
    def test_a_backup_without_a_budgets_table_reads_as_no_budgets(self):
        """Older exports predate the table. Budgets are additive — never an error."""
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        conn = sqlite3.connect(tmp.name)
        conn.execute("CREATE TABLE wallets (wallet_pk TEXT PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()
        with open(tmp.name, "rb") as fh:
            content = fh.read()
        os.unlink(tmp.name)
        self.assertEqual(read_budgets(content), [])

    def test_start_date_converts_in_the_site_timezone(self):
        """1753988400 is 2025-08-01T00:00:00+05:00. A UTC conversion lands on
        2025-07-31 and shifts every cycle boundary that follows."""
        budget = read_budgets(_build_sqlite())[0]
        self.assertEqual(budget["start_date"], "2025-08-01")

    def test_end_date_is_not_read(self):
        """end_date ends the FIRST period only. Deriving a window from it marks
        every live budget expired."""
        budget = read_budgets(_build_sqlite())[0]
        self.assertNotIn("end_date", budget)
        self.assertEqual(budget["is_archived"], 0)

    def test_null_wallet_fks_means_all_wallets_not_the_scalar_wallet_fk(self):
        """C5.1: the scalar wallet_fk is a display anchor. Reading it as the scope
        silently narrows the budget to one account and understates its actuals."""
        budget = read_budgets(_build_sqlite())[0]
        self.assertEqual(budget["wallet_scope"], [])

    def test_wallet_fks_resolves_to_names(self):
        content = _build_sqlite({"wallet_fks": json.dumps(["w-uuid"])})
        self.assertEqual(
            read_budgets(content)[0]["wallet_scope"],
            [{"pk": "w-uuid", "wallet": "Saving"}],
        )

    def test_integer_like_pks_survive_as_strings(self):
        """C5.3: seeded Cashew records use small integer-string PKs. A UUID parse
        or an int cast drops that leg of the scope entirely."""
        budget = read_budgets(_build_sqlite())[0]
        self.assertEqual(
            budget["category_scope"],
            [{"pk": "5", "category": "Entertainment", "sub_category": ""}],
        )

    def test_a_sub_category_resolves_to_its_parent_pair(self):
        """The mapping table keys on (parent name, own name). A flat pk→name
        lookup files every sub-category under a parent it does not have."""
        content = _build_sqlite({"category_fks": json.dumps(["s-uuid"])})
        self.assertEqual(
            read_budgets(content)[0]["category_scope"],
            [{"pk": "s-uuid", "category": "Food", "sub_category": "Coffee"}],
        )

    def test_an_unknown_reoccurrence_raises(self):
        """D3.d: the enum is only partially known. Bucketing an unknown value as
        monthly produces a budget chart that is wrong but plausible."""
        content = _build_sqlite({"reoccurrence": 99})
        with self.assertRaises(frappe.ValidationError):
            read_budgets(content)

    def test_budget_transaction_filters_is_not_stored(self):
        """C5.5: the enum is undocumented and unresolvable from data, so it must
        not reach anything that could act on it."""
        budget = read_budgets(_build_sqlite())[0]
        self.assertNotIn("budget_transaction_filters", budget)


class TestResolveScope(FrappeTestCase):
    CATEGORY_MAP = {
        ("Food", ""): {"default_account": "Food - X", "category_type": "Expense"},
        ("Fuel", ""): {"default_account": "Fuel - X", "category_type": "Expense"},
    }
    ACCOUNT_MAP = {"Saving": "Saving - X", "Petty Cash": "Cash - X"}

    def _budget(self, **kwargs):
        base = {"category_scope": [], "category_exclude": [], "wallet_scope": []}
        base.update(kwargs)
        return base

    def test_an_unmapped_category_blocks_the_budget(self):
        """Decision 6: an unmapped scope member is a hole in the figure, and it
        fails in the dangerous direction — the limit reads UNDER when it is blown."""
        scope = resolve_scope(
            self._budget(category_scope=[{"pk": "9", "category": "Travel", "sub_category": ""}]),
            self.CATEGORY_MAP, self.ACCOUNT_MAP,
        )
        self.assertEqual([u["kind"] for u in scope["unresolved"]], ["category"])

    def test_a_category_only_mapping_covers_a_sub_category(self):
        scope = resolve_scope(
            self._budget(category_scope=[{"pk": "s", "category": "Food", "sub_category": "Coffee"}]),
            self.CATEGORY_MAP, self.ACCOUNT_MAP,
        )
        self.assertEqual(scope["unresolved"], [])
        self.assertEqual([a["account"] for a in scope["accounts"]], ["Food - X"])

    def test_an_empty_category_scope_expands_to_every_mapped_category(self):
        scope = resolve_scope(self._budget(), self.CATEGORY_MAP, self.ACCOUNT_MAP)
        self.assertEqual(
            sorted(a["account"] for a in scope["accounts"]), ["Food - X", "Fuel - X"]
        )

    def test_an_exclude_removes_a_category_from_the_expanded_scope(self):
        scope = resolve_scope(
            self._budget(category_exclude=[{"pk": "f", "category": "Fuel", "sub_category": ""}]),
            self.CATEGORY_MAP, self.ACCOUNT_MAP,
        )
        self.assertEqual([a["account"] for a in scope["accounts"]], ["Food - X"])

    def test_an_unmapped_exclude_does_not_block_the_budget(self):
        """Excluding something unmapped removes nothing from a figure built only
        from mapped accounts, so it cannot be a hole."""
        scope = resolve_scope(
            self._budget(category_exclude=[{"pk": "z", "category": "Travel", "sub_category": ""}]),
            self.CATEGORY_MAP, self.ACCOUNT_MAP,
        )
        self.assertEqual(scope["unresolved"], [])

    def test_an_unmapped_wallet_blocks_the_budget(self):
        scope = resolve_scope(
            self._budget(wallet_scope=[{"pk": "w", "wallet": "Meezan"}]),
            self.CATEGORY_MAP, self.ACCOUNT_MAP,
        )
        self.assertEqual([u["kind"] for u in scope["unresolved"]], ["account"])

    def test_an_empty_wallet_scope_expands_to_every_mapped_account(self):
        scope = resolve_scope(self._budget(), self.CATEGORY_MAP, self.ACCOUNT_MAP)
        self.assertEqual(
            sorted(w["account"] for w in scope["wallets"]), ["Cash - X", "Saving - X"]
        )

    def test_a_deleted_category_master_blocks_the_budget(self):
        """read_budgets leaves `category` None when the PK resolves to nothing."""
        scope = resolve_scope(
            self._budget(category_scope=[{"pk": "gone", "category": None, "sub_category": ""}]),
            self.CATEGORY_MAP, self.ACCOUNT_MAP,
        )
        self.assertEqual([u["kind"] for u in scope["unresolved"]], ["category"])
