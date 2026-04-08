"""
Unit tests for C002 — CSV Parser + Normalizer.

Fixture data is lifted verbatim from cashew-2026-04-08-21-22-58-504687.csv,
covering all classification branches: Income, Expense, Transfer pair (same-
currency PKR), Transfer pair (cross-currency USD→PKR), and missing-column /
empty-file error paths.

Run:  bench --site work.local run-tests --module cashew_integration.tests.test_parser
"""
import hashlib
import json

from frappe.tests.utils import FrappeTestCase

from cashew_integration.importer.parser import (
    REQUIRED_COLUMNS,
    _compute_hash,
    parse_csv,
)

# ── fixture CSV ────────────────────────────────────────────────────────────────
# 7 data rows sampled directly from the real export.
# Multi-line notes use a real newline inside the CSV quoted field.
HEADER = (
    "account,amount,currency,title,note,date,income,type,"
    "category name,subcategory name,color,icon,emoji,budget,objective\n"
)

# PKR same-currency internal transfer pair (rows 1-2 in the real export)
ROW_SAVING_IN = (
    'Saving,120000.0,PKR,Saving,'
    '"Transferred Balance\nPetty Cash \u2192 Saving",'
    '2026-04-08 20:27:31.000,true,null,Balance Correction,,0xff607d8b,charts.png,,,\n'
)
ROW_PETTY_OUT = (
    'Petty Cash,-120000.0,PKR,Saving,'
    '"Transferred Balance\nPetty Cash \u2192 Saving",'
    '2026-04-08 20:27:30.000,false,null,Balance Correction,,0xff607d8b,charts.png,,,\n'
)
# Plain PKR income + expense rows
ROW_FREELANCE = (
    'Petty Cash,42000.0,PKR,March,,2026-04-08 20:25:07.000,true,null,'
    'Freelance,,,dollar-coin.png,,,\n'
)
ROW_ENTERTAINMENT = (
    'Petty Cash,-2240.0,PKR,Fast food,,2026-04-08 19:00:18.000,false,null,'
    'Entertainment,,0xff2196f3,popcorn.png,,,\n'
)
# USD income row (foreign currency)
ROW_NSAVE_USD = (
    'NSave,423.0,USD,,,2026-04-07 13:15:06.000,true,null,'
    'Freelance,,,dollar-coin.png,,,\n'
)
# Cross-currency transfer pair (NSave USD → Petty Cash PKR, rows 25-26)
ROW_PETTY_XFER_IN = (
    'Petty Cash,9522.79091992,PKR,Petty Cash Transfer In,'
    '"Transferred Balance\nNSave \u2192 Petty Cash",'
    '2026-03-26 22:53:31.000,true,null,Balance Correction,,0xff607d8b,charts.png,,,\n'
)
ROW_NSAVE_XFER_OUT = (
    'NSave,-34.0,USD,NSave Transfer Out,'
    '"Transferred Balance\nNSave \u2192 Petty Cash",'
    '2026-03-26 22:53:30.000,false,null,Balance Correction,,0xff607d8b,charts.png,,,\n'
)

FULL_CSV = (
    HEADER
    + ROW_SAVING_IN
    + ROW_PETTY_OUT
    + ROW_FREELANCE
    + ROW_ENTERTAINMENT
    + ROW_NSAVE_USD
    + ROW_PETTY_XFER_IN
    + ROW_NSAVE_XFER_OUT
)


def _csv(*rows: str) -> bytes:
    return (HEADER + "".join(rows)).encode("utf-8")


class TestParserColumnMapping(FrappeTestCase):
    """Every required column is read and converted to the correct output key."""

    def setUp(self):
        self.rows = parse_csv(FULL_CSV.encode("utf-8"), "PKR")

    def test_all_required_columns_present_produces_rows(self):
        self.assertEqual(len(self.rows), 7)

    def test_expense_row_field_mapping(self):
        row = next(r for r in self.rows if r["raw_account"] == "Petty Cash"
                   and r["title"] == "Fast food")
        self.assertEqual(row["raw_account"], "Petty Cash")
        self.assertEqual(row["raw_amount"], 2240.0)    # abs value
        self.assertEqual(row["source_currency"], "PKR")
        self.assertEqual(row["title"], "Fast food")
        self.assertEqual(row["category"], "Entertainment")
        self.assertEqual(row["txn_date"], "2026-04-08")
        self.assertEqual(row["raw_txn_time"], "19:00:18")
        self.assertEqual(row["month_key"], "2026-04")
        self.assertEqual(row["income_flag"], "false")
        self.assertEqual(row["txn_type"], "Expense")
        self.assertEqual(row["item_label"], "Entertainment | 2026-04")

    def test_income_flag_sets_txn_type_income(self):
        row = next(r for r in self.rows if r["raw_account"] == "Petty Cash"
                   and r["title"] == "March")
        self.assertEqual(row["txn_type"], "Income")
        self.assertEqual(row["raw_amount"], 42000.0)

    def test_same_currency_exchange_rate_defaulted_to_one(self):
        row = next(r for r in self.rows if r["title"] == "Fast food")
        self.assertEqual(row["exchange_rate"], 1.0)
        self.assertEqual(row["base_amount"], 2240.0)

    def test_foreign_currency_exchange_rate_is_none(self):
        row = next(r for r in self.rows if r["source_currency"] == "USD"
                   and r["title"] == "")
        self.assertIsNone(row["exchange_rate"])

    def test_missing_required_column_raises(self):
        bad_csv = (
            "account,amount,currency,title,note,date,income\n"   # missing category name etc.
            "Petty Cash,100.0,PKR,test,,2026-01-01 00:00:00,false\n"
        ).encode("utf-8")
        with self.assertRaises(Exception):   # frappe.throw raises frappe.ValidationError
            parse_csv(bad_csv, "PKR")

    def test_empty_file_raises(self):
        empty = (HEADER).encode("utf-8")
        with self.assertRaises(Exception):
            parse_csv(empty, "PKR")

    def test_row_idx_is_one_based(self):
        for i, row in enumerate(self.rows, start=1):
            self.assertEqual(row["row_idx"], i)

    def test_all_valid_rows_have_source_hash(self):
        for row in self.rows:
            if row["validation_status"] == "Valid":
                self.assertIsNotNone(row.get("source_hash"))
                self.assertEqual(len(row["source_hash"]), 64)   # SHA-256 hex


class TestParserHashCorrectness(FrappeTestCase):
    """SHA-256 hash is deterministic, field-sensitive, and uses full-precision amount."""

    def _reference_hash(self, account, amount_float, currency, date_str,
                        income, category, subcategory, title, note) -> str:
        payload = {
            "account":     account,
            "amount":      str(round(abs(amount_float), 10)),
            "currency":    currency,
            "date":        date_str,
            "income":      income,
            "category":    category,
            "subcategory": subcategory,
            "title":       title,
            "note":        note,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    def test_hash_is_deterministic(self):
        rows_a = parse_csv(FULL_CSV.encode(), "PKR")
        rows_b = parse_csv(FULL_CSV.encode(), "PKR")
        for a, b in zip(rows_a, rows_b):
            if a.get("source_hash"):
                self.assertEqual(a["source_hash"], b["source_hash"])

    def test_hash_matches_reference_implementation(self):
        rows = parse_csv(_csv(ROW_ENTERTAINMENT), "PKR")
        row = rows[0]
        expected = self._reference_hash(
            account="Petty Cash",
            amount_float=-2240.0,
            currency="PKR",
            date_str="2026-04-08",
            income="false",
            category="Entertainment",
            subcategory="",
            title="Fast food",
            note="",
        )
        self.assertEqual(row["source_hash"], expected)

    def test_hash_uses_full_precision_amount(self):
        """9522.79091992 must hash differently than its 2-decimal truncation 9522.79."""
        rows = parse_csv(_csv(ROW_PETTY_XFER_IN), "PKR")
        row = rows[0]   # classification pass runs on single row; no pairing here

        full_precision_hash = row["source_hash"]

        # What the hash would be if only 2 decimals were used
        truncated_payload = {
            "account":     "Petty Cash",
            "amount":      str(round(9522.79091992, 2)),   # "9522.79"
            "currency":    "PKR",
            "date":        "2026-03-26",
            "income":      "true",
            "category":    "Balance Correction",
            "subcategory": "",
            "title":       "Petty Cash Transfer In",
            "note":        "Transferred Balance\nNSave \u2192 Petty Cash",
        }
        truncated_hash = hashlib.sha256(
            json.dumps(truncated_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        self.assertNotEqual(full_precision_hash, truncated_hash,
                            "Full-precision amount must produce a different hash than 2-decimal truncation.")

    def test_different_rows_produce_different_hashes(self):
        rows = parse_csv(FULL_CSV.encode(), "PKR")
        valid_hashes = [r["source_hash"] for r in rows if r.get("source_hash")]
        self.assertEqual(len(valid_hashes), len(set(valid_hashes)),
                         "Every row must have a unique source_hash.")


class TestParserBalanceCorrectionClassification(FrappeTestCase):
    """Transfer rows are classified into Transfer / External Transfer / Adjustment."""

    def test_pkr_pair_classified_as_internal_transfer(self):
        """Both legs of the PKR Saving ↔ Petty Cash pair must become Transfer."""
        rows = parse_csv(_csv(ROW_SAVING_IN, ROW_PETTY_OUT), "PKR")
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["txn_type"], "Transfer",
                             f"Row {row['row_idx']} should be Transfer, got {row['txn_type']}")

    def test_pkr_pair_legs_are_linked_by_row_idx(self):
        rows = parse_csv(_csv(ROW_SAVING_IN, ROW_PETTY_OUT), "PKR")
        by_idx = {r["row_idx"]: r for r in rows}
        for row in rows:
            partner_idx = row.get("transfer_pair_row_idx")
            self.assertIsNotNone(partner_idx,
                                 f"Row {row['row_idx']} has no transfer_pair_row_idx.")
            partner = by_idx[partner_idx]
            self.assertEqual(partner.get("transfer_pair_row_idx"), row["row_idx"],
                             "Pair links must be symmetric.")

    def test_cross_currency_pair_classified_as_internal_transfer(self):
        """NSave(USD) → Petty Cash(PKR) — both accounts present → Transfer."""
        rows = parse_csv(_csv(ROW_PETTY_XFER_IN, ROW_NSAVE_XFER_OUT), "PKR")
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual(row["txn_type"], "Transfer",
                             f"Row {row['row_idx']} should be Transfer, got {row['txn_type']}")

    def test_external_transfer_when_partner_not_in_file(self):
        """A single Balance Correction leg with no partner → External Transfer."""
        solo_leg = (
            'NSave,-34.0,USD,NSave Transfer Out,'
            '"Transferred Balance\nNSave \u2192 ExternalBank",'  # ExternalBank not in file
            '2026-03-26 22:53:30.000,false,null,Balance Correction,,,,,,\n'
        )
        rows = parse_csv(_csv(solo_leg), "PKR")
        self.assertEqual(rows[0]["txn_type"], "External Transfer")

    def test_balance_correction_without_paired_note_is_adjustment(self):
        """Balance Correction row with no 'Transferred Balance' note → Adjustment."""
        adj_row = (
            'Petty Cash,-3.0,PKR,,'
            ',2026-03-29 21:32:49.000,false,null,Balance Correction,,,,,,\n'
        )
        rows = parse_csv(_csv(adj_row), "PKR")
        self.assertEqual(rows[0]["txn_type"], "Adjustment")
