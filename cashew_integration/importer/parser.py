"""
C002 — CSV Parser + Normalizer

Parses a Cashew CSV export into a list of row dicts ready for mapping (C003).
Responsibilities:
  - File-level pre-validation (encoding, required columns, at least one row)
  - Column normalisation (trim, type-convert, hash, datetime split)
  - Initial txn_type assignment (Income / Expense / Transfer placeholder)
  - Balance Correction / Balance Transfer classification pass
    (paired Transfer, External Transfer, Adjustment)
"""

import csv
import hashlib
import io
import json
import re
from datetime import datetime

import frappe

# ── constants ──────────────────────────────────────────────────────────────────

TRANSFER_CATEGORIES = {"Balance Correction", "Balance Transfer"}

REQUIRED_COLUMNS = {
    "account",
    "amount",
    "currency",
    "title",
    "note",
    "date",
    "income",
    "category name",
    "subcategory name",
}

_TRANSFER_NOTE_RE = re.compile(
    r"^Transferred Balance\n(.+)\s→\s(.+)$", re.DOTALL
)


# ── public entry point ─────────────────────────────────────────────────────────

def parse_csv(file_content: bytes, company_currency: str) -> list[dict]:
    """
    Parse *file_content* (raw bytes from an uploaded Cashew CSV) and return a
    list of normalised row dicts.

    Raises ``frappe.ValidationError`` with a structured error code on any
    file-level failure (encoding, missing columns, empty file).

    Row-level parse errors are stored inside each row dict as
    ``validation_status = "Error"`` + ``validation_error_code`` rather than
    raised, so the caller can show them in the preview.
    """
    text = _decode(file_content)
    reader = _make_reader(text)
    headers = _validate_headers(reader)
    rows = _parse_rows(reader, headers, company_currency)
    if not rows:
        frappe.throw("The CSV file contains no data rows.", frappe.ValidationError,
                     title="FILE_EMPTY")
    _classify_transfer_rows(rows)
    return rows


# ── decoding ───────────────────────────────────────────────────────────────────

def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    frappe.throw(
        "The CSV file must be UTF-8 encoded. Please re-export from Cashew.",
        frappe.ValidationError,
        title="FILE_ENCODING_ERROR",
    )


def _make_reader(text: str):
    return csv.DictReader(io.StringIO(text))


def _validate_headers(reader: csv.DictReader) -> list[str]:
    if reader.fieldnames is None:
        frappe.throw("The CSV file is empty.", frappe.ValidationError, title="FILE_EMPTY")
    lowered = {h.strip().lower() for h in reader.fieldnames}
    if _is_summary_export(lowered):
        frappe.throw(
            "This file looks like a Cashew summary/pivot export (for example, "
            "'Row Labels' / 'Sum of amount'), not the raw transaction export. "
            "Please export transactions directly from Cashew (Settings -> Export) "
            "and upload that CSV.",
            frappe.ValidationError,
            title="FILE_WRONG_EXPORT_TYPE",
        )
    missing = REQUIRED_COLUMNS - lowered
    if missing:
        frappe.throw(
            f"CSV is missing required columns: {', '.join(sorted(missing))}. "
            "Please export the file directly from the Cashew app "
            "(Settings → Export) and attach that file.",
            frappe.ValidationError,
            title="FILE_MISSING_COLUMNS",
        )
    return reader.fieldnames


def _is_summary_export(headers_lowered: set[str]) -> bool:
    return "row labels" in headers_lowered and "sum of amount" in headers_lowered


# ── row parsing ────────────────────────────────────────────────────────────────

def _parse_rows(reader: csv.DictReader, headers, company_currency: str) -> list[dict]:
    rows = []
    for idx, raw in enumerate(reader, start=1):
        row = _parse_single_row(idx, raw, company_currency)
        rows.append(row)
    return rows


def _parse_single_row(idx: int, raw: dict, company_currency: str) -> dict:
    row = {
        "row_idx": idx,
        "validation_status": "Valid",
        "validation_error_code": None,
        "validation_error_message": None,
    }

    # ── date / time ────────────────────────────────────────────────────────────
    raw_date = (raw.get("date") or "").strip()
    if not raw_date:
        return _error(row, "MISSING_DATE", "Transaction date is empty.")
    try:
        dt = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        try:
            dt = datetime.strptime(raw_date, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return _error(row, "MISSING_DATE",
                          f"Cannot parse date '{raw_date}'. Expected YYYY-MM-DD HH:MM:SS.mmm")
    row["txn_date"] = dt.date().isoformat()
    row["raw_txn_time"] = dt.time().isoformat()
    row["month_key"] = dt.strftime("%Y-%m")

    # ── amount ─────────────────────────────────────────────────────────────────
    raw_amount_str = (raw.get("amount") or "").strip()
    if not raw_amount_str:
        return _error(row, "MISSING_AMOUNT", "Amount is empty.")
    try:
        raw_amount_float = float(raw_amount_str)
    except ValueError:
        return _error(row, "MISSING_AMOUNT",
                      f"Amount '{raw_amount_str}' is not a valid number.")
    if raw_amount_float == 0:
        return _error(row, "MISSING_AMOUNT", "Amount must not be zero.")
    row["raw_amount"] = round(abs(raw_amount_float), 2)

    # ── category ───────────────────────────────────────────────────────────────
    category = (raw.get("category name") or "").strip()
    if not category:
        return _error(row, "MISSING_CATEGORY", "Category is empty.")
    row["category"] = category
    row["sub_category"] = (raw.get("subcategory name") or "").strip()

    # ── string fields ──────────────────────────────────────────────────────────
    row["raw_account"] = (raw.get("account") or "").strip()
    row["title"] = (raw.get("title") or "").strip()
    row["note"] = (raw.get("note") or "").strip()
    row["source_currency"] = (raw.get("currency") or "").strip()
    row["company_currency"] = company_currency
    row["income_flag"] = (raw.get("income") or "").strip().lower()
    if row["income_flag"] not in {"true", "false"}:
        return _error(
            row,
            "INVALID_INCOME_FLAG",
            f"Income flag '{row['income_flag']}' is invalid; must be 'true' or 'false'.",
        )

    # ── item_label ─────────────────────────────────────────────────────────────
    row["item_label"] = f"{category} | {row['month_key']}"

    # ── txn_type (initial pass) ────────────────────────────────────────────────
    if category in TRANSFER_CATEGORIES:
        row["txn_type"] = "Transfer"   # overwritten by classification pass
    elif row["income_flag"] == "true":
        row["txn_type"] = "Income"
    else:
        row["txn_type"] = "Expense"

    # ── exchange_rate / base_amount defaults ───────────────────────────────────
    row["exchange_rate"] = None
    row["base_amount"] = 0.0
    if row["source_currency"] == company_currency:
        row["exchange_rate"] = 1.0
        row["base_amount"] = row["raw_amount"]

    # ── source hash (full-precision amount in hash) ────────────────────────────
    row["source_hash"] = _compute_hash(row, raw_amount_float)

    return row


# ── hash ───────────────────────────────────────────────────────────────────────

def _compute_hash(row: dict, raw_amount_float: float) -> str:
    payload = {
        "account":      row["raw_account"],
        "amount":       str(round(abs(raw_amount_float), 10)),
        "currency":     row["source_currency"],
        "date":         row["txn_date"],
        "income":       row["income_flag"],
        "category":     row["category"],
        "subcategory":  row["sub_category"],
        "title":        row["title"],
        "note":         row["note"],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


# ── transfer classification pass ───────────────────────────────────────────────

def _classify_transfer_rows(rows: list[dict]) -> None:
    """
    Classify every row whose initial txn_type is "Transfer" into:
      - "Transfer"          — valid paired internal transfer
      - "External Transfer" — one leg, partner account external to the file
      - "Adjustment"        — "Updated Total Balance", no note, or any other
                              format that doesn't match the paired-transfer note

    Mutates rows in-place.
    """
    transfer_rows = [
        r for r in rows
        if r.get("txn_type") == "Transfer" and r.get("validation_status") == "Valid"
    ]

    if not transfer_rows:
        return

    # all raw_account values present in the file (for partner-exists check)
    all_accounts_in_file = {
        (r.get("raw_account") or "").strip()
        for r in rows
        if (r.get("raw_account") or "").strip()
    }

    # index by row_idx for O(1) lookup when linking pair partners
    by_idx = {r["row_idx"]: r for r in rows}

    # Step 1 — note pattern detection
    for row in transfer_rows:
        m = _TRANSFER_NOTE_RE.match(row["note"])
        if m:
            row["_note_type"] = "paired_transfer"
            row["_transfer_source_name"] = m.group(1).strip()
            row["_transfer_dest_name"] = m.group(2).strip()
        else:
            row["_note_type"] = "adjustment"

    # Step 2 — classify adjustments first (simple)
    for row in transfer_rows:
        if row["_note_type"] == "adjustment":
            row["txn_type"] = "Adjustment"
            row["resolved_route"] = "Adjustment JE"

    # Step 3 — group paired_transfer rows by (note, date)
    paired = [r for r in transfer_rows if r["_note_type"] == "paired_transfer"]
    groups: dict[tuple, list[dict]] = {}
    for row in paired:
        key = (row["note"].strip(), row["txn_date"])
        groups.setdefault(key, []).append(row)

    for key, group in groups.items():
        if len(group) != 2:
            # incomplete pair — only block if partner account exists in the file
            for row in group:
                partner = _partner_account(row)
                if partner in all_accounts_in_file:
                    _error(row, "TRANSFER_PAIR_INCOMPLETE",
                           f"Transfer pair has {len(group)} leg(s); expected exactly 2.")
                else:
                    # partner is external — treat each standalone leg as External Transfer
                    row["txn_type"] = "External Transfer"
                    row["resolved_external_account"] = None  # resolved in C003
            continue

        leg_a, leg_b = group
        # identify source (income_flag=false) and dest (income_flag=true)
        source_leg = leg_a if leg_a["income_flag"] == "false" else leg_b
        dest_leg   = leg_a if leg_a["income_flag"] == "true"  else leg_b

        # check whether partner account is in the file
        source_partner = _partner_account(source_leg)
        dest_partner   = _partner_account(dest_leg)

        partner_in_file = (
            source_partner in all_accounts_in_file
            and dest_partner in all_accounts_in_file
        )

        if partner_in_file:
            source_leg["txn_type"] = "Transfer"
            dest_leg["txn_type"]   = "Transfer"
            source_leg["transfer_pair_row_idx"] = dest_leg["row_idx"]
            dest_leg["transfer_pair_row_idx"]   = source_leg["row_idx"]
        else:
            # at least one partner external
            for row in group:
                row["txn_type"] = "External Transfer"
                row["resolved_external_account"] = None  # C003 resolves from mapping

    # clean up temporary classification keys
    for row in transfer_rows:
        row.pop("_note_type", None)
        row.pop("_transfer_source_name", None)
        row.pop("_transfer_dest_name", None)


def _partner_account(row: dict) -> str:
    """Return the partner account name from the transfer note."""
    m = _TRANSFER_NOTE_RE.match(row.get("note", ""))
    if not m:
        return ""
    source_name = m.group(1).strip()
    dest_name   = m.group(2).strip()
    # the partner is whichever side is NOT this row's own account
    if row["raw_account"] == source_name:
        return dest_name
    return source_name


# ── helpers ────────────────────────────────────────────────────────────────────

def _error(row: dict, code: str, message: str) -> dict:
    row["validation_status"] = "Error"
    row["validation_error_code"] = code
    row["validation_error_message"] = message
    return row
