"""
f011 c001 — Cashew SQLite Reader

Second ingestion path (alongside the CSV parser, f001). Reads a Cashew SQLite
backup ("SQL file") directly and returns the **exact same** list of normalized
row dicts that ``parser.parse_csv`` returns, so everything downstream of the
``api.parse_and_preview`` seam — mapping, validation, idempotency, the async
worker, posting, diagnostics, and the SPA — is reused with zero change.

The single hard requirement is ``source_hash`` PARITY: the same transaction read
from CSV and from SQL must hash identically, or "add alongside" double-posts. The
shared ``parser._compute_hash`` is the one hash implementation both readers call;
every normalization rule below (currency ``.upper()``, epoch→site-local date,
``.strip()``, income→``"true"``/``"false"``, full-precision amount) exists to hold
that parity against the CSV export's string shapes.

Transfer pairing DIVERGES from the CSV path: it is driven by the DB's
authoritative ``paired_transaction_fk`` rather than the CSV's note+time heuristic
(which can mis-pair repeated same-note same-day transfers into balanced-but-wrong
JVs the per-row hash gate can't catch). See ``_apply_fk_pairing``.
"""

import os
import sqlite3
import tempfile
from datetime import datetime, timezone

import pytz

import frappe
from frappe.utils import get_system_timezone

from cashew_integration.importer.parser import (
    _compute_hash,
    _assign_txn_type,
    _classify_transfer_rows,
)
from cashew_integration.importer.category_lookup import build_category_type_map
from cashew_integration.importer.errors import set_row_validation_error

# ── reader query — LEFT JOIN mandatory (INNER would silently drop rows whose ────
# wallet/category was deleted, re-creating the exact omission bug this fixes),
# WHERE paid=1 is the balance-scope filter, deterministic order for stable row_idx.
_READER_SQL = """
SELECT t.transaction_pk, t.name, t.amount, t.note, t.income, t.date_created,
       t.paired_transaction_fk,
       w.name AS account, w.currency,
       c.name AS category, sc.name AS sub_category
FROM transactions t
LEFT JOIN wallets    w  ON t.wallet_fk       = w.wallet_pk
LEFT JOIN categories c  ON t.category_fk     = c.category_pk
LEFT JOIN categories sc ON t.sub_category_fk = sc.category_pk
WHERE t.paid = 1
ORDER BY t.date_created, t.transaction_pk;
"""

_DEFAULT_TZ = "Asia/Karachi"


# ── public entry point ─────────────────────────────────────────────────────────

def read_sqlite(
    file_content: bytes,
    company_currency: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """Read a Cashew SQLite backup and return normalized row dicts.

    Same output contract as ``parser.parse_csv`` (see ``sql-import-plan.md`` §2).
    ``from_date`` / ``to_date`` are optional inclusive **site-local** calendar
    bounds (``YYYY-MM-DD``); blank/blank imports the whole DB.
    """
    if from_date and to_date and str(from_date) > str(to_date):
        frappe.throw(
            f"Import 'from' date ({from_date}) is after 'to' date ({to_date}).",
            frappe.ValidationError,
            title="SQL_DATE_WINDOW_INVALID",
        )

    tz = pytz.timezone(get_system_timezone() or _DEFAULT_TZ)
    lo = str(from_date) if from_date else None
    hi = str(to_date) if to_date else None
    raw_rows = _fetch_rows(file_content)

    rows: list[dict] = []
    for raw in raw_rows:
        row = _normalize_row(raw, company_currency, tz, lo, hi)
        if row is None:
            continue  # outside the date window
        rows.append(row)

    # stable 1-based row_idx over the kept, ordered set (error rows included)
    for idx, row in enumerate(rows, start=1):
        row["row_idx"] = idx

    # txn_type + note/adjustment/external routing via the SHARED CSV helpers …
    category_map = build_category_type_map()
    for row in rows:
        if row.get("validation_status") == "Error":
            continue
        _assign_txn_type(row, category_map)
    _classify_transfer_rows(rows)

    # … then FK-authoritative transfer pairing OVERRIDES the classifier's pairing.
    _apply_fk_pairing(rows)

    return rows


# ── db access ──────────────────────────────────────────────────────────────────

def _fetch_rows(file_content: bytes) -> list[sqlite3.Row]:
    """Open the uploaded bytes as a read-only SQLite DB and run the reader query.

    ``sqlite3`` needs a path, so the bytes are written to a temp file, opened
    read-only (never mutate the uploaded backup), and cleaned up in ``finally``.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    try:
        tmp.write(file_content)
        tmp.flush()
        tmp.close()
        conn = sqlite3.connect(f"file:{tmp.name}?mode=ro", uri=True)
        try:
            conn.row_factory = sqlite3.Row
            return conn.execute(_READER_SQL).fetchall()
        except sqlite3.DatabaseError:
            frappe.throw(
                "The attached file is not a readable Cashew SQLite backup. "
                "Export a fresh backup from Cashew (Settings → Backups) and attach it.",
                frappe.ValidationError,
                title="SQL_FILE_UNREADABLE",
            )
        finally:
            conn.close()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


# ── per-row normalization (parity-critical) ────────────────────────────────────

def _normalize_row(
    raw: sqlite3.Row, company_currency: str, tz, lo: str | None, hi: str | None
) -> dict | None:
    """Map one SQLite row to the normalized dict. Returns ``None`` when the row's
    site-local date falls outside the requested inclusive window (caller skips it).
    ``lo``/``hi`` are ISO ``YYYY-MM-DD`` strings or ``None`` (no bound)."""
    # epoch (UTC seconds) → site-local datetime  ⚠ #1 parity trap
    local_dt = datetime.fromtimestamp(int(raw["date_created"]), tz=timezone.utc).astimezone(tz)
    local_date = local_dt.date()

    # date-window filter on the SITE-LOCAL date (never an epoch-range SQL compare —
    # that risks an off-by-one at the tz boundary); ISO date strings sort correctly.
    iso = local_date.isoformat()
    if (lo and iso < lo) or (hi and iso > hi):
        return None

    account = raw["account"]
    category = raw["category"]

    row: dict = {
        # row_idx assigned by caller after windowing
        "validation_status": "Valid",
        "validation_error_code": None,
        "validation_error_message": None,
        "txn_date": local_date.isoformat(),
        "raw_txn_time": local_dt.time().isoformat(),
        "month_key": local_dt.strftime("%Y-%m"),
        "raw_account": (account or "").strip(),
        "title": (raw["name"] or "").strip(),
        "note": (raw["note"] or "").strip(),   # keep interior \n (transfer regex needs it)
        "source_currency": (raw["currency"] or "").strip().upper(),  # DB pkr/usd → PKR/USD
        "company_currency": company_currency,
        "category": category or "",
        "sub_category": (raw["sub_category"] or ""),
        # direction from the income column, NOT the sign of amount
        "income_flag": "true" if int(raw["income"]) == 1 else "false",
        # carried for the FK pairing pass; not persisted to the child (leading _)
        "_paired_fk": raw["paired_transaction_fk"] or None,
        "_txn_pk": raw["transaction_pk"],
    }

    amount_float = float(raw["amount"])
    row["raw_amount"] = round(abs(amount_float), 2)
    row["item_label"] = f"{row['category']} | {row['month_key']}"
    # placeholder; overwritten by _assign_txn_type / _classify_transfer_rows
    row["txn_type"] = "Income" if row["income_flag"] == "true" else "Expense"

    # exchange defaults mirror parser._parse_single_row
    row["exchange_rate"] = None
    row["base_amount"] = 0.0
    if row["source_currency"] == company_currency:
        row["exchange_rate"] = 1.0
        row["base_amount"] = row["raw_amount"]

    # master unresolved after LEFT JOIN → ERROR row, never a silent drop
    if account is None or category is None:
        missing = "wallet" if account is None else "category"
        set_row_validation_error(
            row,
            "SQL_MASTER_UNRESOLVED",
            f"SQLite {missing} could not be resolved for transaction "
            f"{raw['transaction_pk']} (deleted master?).",
        )
        # still hash it so a later re-resolve stays idempotent
        row["source_hash"] = _compute_hash(row, amount_float)
        return row

    # source hash — full-precision amount via the SHARED helper (parity insurance)
    row["source_hash"] = _compute_hash(row, amount_float)
    return row


# ── FK-driven transfer pairing (deliberate divergence — runs AFTER classifier) ──

def _apply_fk_pairing(rows: list[dict]) -> None:
    """Override the note+time pairing done by ``_classify_transfer_rows`` with the
    DB's authoritative ``paired_transaction_fk``. Runs LAST because the classifier
    re-pairs by note+time and would otherwise clobber FK-set ``transfer_pair_row_idx``.

    - FK partner in the kept set → internal Transfer JV (pair both legs); this
      overrides a note+time pairing error the classifier may have raised.
    - FK dangling (partner deleted or filtered out by the date window) → External
      Transfer JE (only one leg is in scope).
    Rows with no FK (e.g. ``Updated Total Balance`` adjustments) are left as the
    classifier routed them. A genuine ``SQL_MASTER_UNRESOLVED`` row is never
    resurrected — that error is a real data problem, not a pairing decision.
    """
    by_pk = {r["_txn_pk"]: r for r in rows}

    for row in rows:
        fk = row.get("_paired_fk")
        if not fk or _is_master_error(row):
            continue
        partner = by_pk.get(fk)
        if partner is not None and not _is_master_error(partner):
            # internal transfer — authoritative pair (clears any pairing error)
            for leg, other in ((row, partner), (partner, row)):
                _clear_pairing_error(leg)
                leg["txn_type"] = "Transfer"
                leg["resolved_route"] = "Transfer JV"
                leg["transfer_pair_row_idx"] = other["row_idx"]
        else:
            # partner not in scope → external, drop any stale pair the classifier set
            _clear_pairing_error(row)
            row["txn_type"] = "External Transfer"
            row["resolved_route"] = "External Transfer JE"
            row["resolved_external_account"] = None
            row["transfer_pair_row_idx"] = None


def _is_master_error(row: dict) -> bool:
    return row.get("validation_error_code") == "SQL_MASTER_UNRESOLVED"


def _clear_pairing_error(row: dict) -> None:
    """Reset a classifier transfer-pairing error (e.g. TRANSFER_PAIR_INCOMPLETE) to
    Valid, since the DB FK is the authoritative pairing signal. No-op otherwise."""
    if row.get("validation_status") == "Error" and not _is_master_error(row):
        row["validation_status"] = "Valid"
        row["validation_error_code"] = None
        row["validation_error_message"] = None
