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

from cashew_integration.importer.category_lookup import build_category_type_map
from cashew_integration.importer.errors import set_row_validation_error

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
    category_map = build_category_type_map()
    for row in rows:
        if row.get("validation_status") == "Error":
            continue
        _assign_txn_type(row, category_map)
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

    # ── txn_type assigned in a second pass (parse_csv) via _assign_txn_type ────
    # Default placeholder so downstream code that reads txn_type before the
    # second pass doesn't KeyError. The placeholder is always overwritten.
    row["txn_type"] = "Income" if row["income_flag"] == "true" else "Expense"

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


# ── txn_type assignment (Decision 1 4-route table) ────────────────────────────

def _assign_txn_type(row: dict, category_map: dict) -> None:
    """Set ``row['txn_type']`` per f006 Decision 1's 4-route table.
    For Loan routes also sets ``row['resolved_route']`` (unambiguous from
    category_type — no posting-threshold fork).

    Called from ``parse_csv`` after rows are parsed and from
    ``api.validate_import`` per row (option-b re-evaluation, so post-parse
    edits to category_type flow through without CSV re-upload).

    Transfer-family rows (category in TRANSFER_CATEGORIES) get the
    ``Transfer`` placeholder — ``_classify_transfer_rows`` refines it later.
    """
    category = row.get("category", "")
    sub      = row.get("sub_category", "") or ""
    income   = row.get("income_flag", "")

    if category in TRANSFER_CATEGORIES:
        row["txn_type"] = "Transfer"
        return

    mapping = category_map.get((category, sub)) or category_map.get((category, ""))
    if mapping is None:
        # Unmapped — direction-based fallback. validate_import surfaces this
        # as CATEGORY_NOT_MAPPED via downstream rules (existing behavior).
        row["txn_type"] = "Income" if income == "true" else "Expense"
        return

    ctype = mapping.get("category_type")
    if ctype == "Income":
        row["txn_type"]       = "Income"
        # Income/Expense always route via Journal Entry (mirrors
        # mapping._resolve_category). Set it here so the re-validate paths
        # (validate_import / row_explorer_revalidate) that call this function
        # re-derive the route too — otherwise a row that ever landed with an
        # empty resolved_route stays stuck at MAPPING_NOT_FOUND forever, since
        # _resolve_category (the only other route-setter) is skipped on
        # re-validate. Only mapped rows reach here, so genuinely unmapped rows
        # still fall through to the MAPPING_NOT_FOUND gate.
        row["resolved_route"] = "Journal Entry"
    elif ctype == "Expense":
        row["txn_type"]       = "Expense"
        row["resolved_route"] = "Journal Entry"
    elif ctype == "Loan Out":
        row["txn_type"]       = "Loan Receivable"
        row["resolved_route"] = "Loan Receivable JE"
    elif ctype == "Loan In":
        row["txn_type"]       = "Loan Payable"
        row["resolved_route"] = "Loan Payable JE"
    else:
        # Future enum values — direction-based fallback so no crash.
        row["txn_type"] = "Income" if income == "true" else "Expense"


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
        # A single (note, date) key can legitimately hold MORE than one transfer:
        # the same transfer repeated on the same day carries an identical note, so
        # N genuine pairs collapse into one group of 2N. Split into source/dest
        # pairs first; only a truly unmatched leg is an incomplete pair. FX
        # transfers scale the two legs differently, so pairing keys off
        # raw_txn_time (the legs post ~1s apart), never on amount.
        pairs, leftovers = _pair_transfer_legs(group)

        for row in leftovers:
            partner = _partner_account(row)
            if partner in all_accounts_in_file:
                _error(row, "TRANSFER_PAIR_INCOMPLETE",
                       "Transfer leg has no matching partner leg "
                       f"(group of {len(group)} under one note/date).")
            else:
                # partner is external — treat each standalone leg as External Transfer
                row["txn_type"] = "External Transfer"
                row["resolved_route"] = "External Transfer JE"
                row["resolved_external_account"] = None  # resolved in C003

        for leg_a, leg_b in pairs:
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
                # Stamp the route here, not only via mapping._resolve_category:
                # the re-validate path re-runs _classify_transfer_rows but NOT
                # _resolve_category, so without this a healed pair stays
                # route-empty and re-trips MAPPING_NOT_FOUND (same class as c012).
                source_leg["resolved_route"] = "Transfer JV"
                dest_leg["resolved_route"]   = "Transfer JV"
                source_leg["transfer_pair_row_idx"] = dest_leg["row_idx"]
                dest_leg["transfer_pair_row_idx"]   = source_leg["row_idx"]
            else:
                # at least one partner external
                for row in (leg_a, leg_b):
                    row["txn_type"] = "External Transfer"
                    row["resolved_route"] = "External Transfer JE"
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


def _pair_transfer_legs(group: list[dict]) -> tuple[list[tuple[dict, dict]], list[dict]]:
    """
    Split transfer legs sharing one (note, date) into source/dest pairs.

    Each pair is one outgoing leg (income_flag "false") matched to one incoming
    leg (income_flag "true"). Matching prefers the nearest raw_txn_time — the two
    legs of a Cashew transfer post ~1s apart — and falls back to row proximity
    when times are absent. Amounts are NOT used: an FX transfer scales the two
    legs differently. Returns (pairs, leftovers); leftovers are legs with no
    partner (odd count, or all-same-direction).
    """
    sources = [r for r in group if r.get("income_flag") == "false"]
    dests   = [r for r in group if r.get("income_flag") == "true"]

    pairs: list[tuple[dict, dict]] = []
    used_dest: set[int] = set()
    for src in sorted(sources, key=lambda r: r["row_idx"]):
        best = None
        for dst in dests:
            if dst["row_idx"] in used_dest:
                continue
            gap = _leg_gap(src, dst)
            if best is None or gap < best[0]:
                best = (gap, dst)
        if best is None:
            continue
        used_dest.add(best[1]["row_idx"])
        pairs.append((src, best[1]))

    matched = {r["row_idx"] for pair in pairs for r in pair}
    leftovers = [r for r in group if r["row_idx"] not in matched]
    return pairs, leftovers


def _leg_time(row: dict):
    """
    Seconds-since-midnight from raw_txn_time, or None when absent/unparseable.

    Handles both shapes the value takes: a "HH:MM:SS" string at parse time (from
    the CSV) and a datetime.timedelta when the row is re-read from the DB on
    re-validate (Frappe Time fields deserialise to timedelta).
    """
    t = row.get("raw_txn_time")
    if not t:
        return None
    if hasattr(t, "total_seconds"):        # datetime.timedelta (DB round-trip)
        return int(t.total_seconds())
    parts = str(t).strip().split(":")
    try:
        h = int(parts[0])
        m = int(parts[1])
        s = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        return None
    return h * 3600 + m * 60 + s


def _leg_gap(a: dict, b: dict) -> tuple:
    """
    Distance between two legs for pair matching. Primary key: |Δ raw_txn_time| in
    seconds when both legs have a time; otherwise fall back to |Δ row_idx|. The
    leading rank (0 vs 1) keeps time matches strictly ahead of index-only ones.
    """
    ta, tb = _leg_time(a), _leg_time(b)
    if ta is not None and tb is not None:
        return (0, abs(ta - tb))
    return (1, abs(a["row_idx"] - b["row_idx"]))


# ── helpers ────────────────────────────────────────────────────────────────────

def _error(row: dict, code: str, message: str) -> dict:
    """Thin shim — delegates to shared helper which stamps `[Row N] ` prefix."""
    set_row_validation_error(row, code, message)
    return row
