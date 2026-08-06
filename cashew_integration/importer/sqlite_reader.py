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

import json
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
#
# `date_time_modified` is selected only when the backup's schema has it. Naming it
# unconditionally makes sqlite raise OperationalError on any older export, which the
# reader reports as "not a readable Cashew SQLite backup" — a wholesale import failure
# in exchange for an optional field. Absent, it reads NULL and _local_modified falls
# back to the created datetime, which is the pre-existing behaviour exactly.
_READER_SQL = """
SELECT t.transaction_pk, t.name, t.amount, t.note, t.income, t.date_created,
       {modified_expr} AS date_time_modified, t.paired_transaction_fk,
       w.name AS account, w.currency,
       c.name AS category, sc.name AS sub_category
FROM transactions t
LEFT JOIN wallets    w  ON t.wallet_fk       = w.wallet_pk
LEFT JOIN categories c  ON t.category_fk     = c.category_pk
LEFT JOIN categories sc ON t.sub_category_fk = sc.category_pk
WHERE t.paid = 1
ORDER BY t.date_created, t.transaction_pk;
"""


def _reader_sql(conn: sqlite3.Connection) -> str:
    columns = {r[1] for r in conn.execute("PRAGMA table_info(transactions)")}
    return _READER_SQL.format(
        modified_expr=(
            "t.date_time_modified" if "date_time_modified" in columns else "NULL"
        )
    )

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

def _with_ro_connection(file_content: bytes, fn):
    """Open the uploaded bytes as a read-only SQLite DB and hand the connection to ``fn``.

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
            return fn(conn)
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


def _fetch_rows(file_content: bytes) -> list[sqlite3.Row]:
    return _with_ro_connection(
        file_content, lambda conn: conn.execute(_reader_sql(conn)).fetchall()
    )


# ── per-row normalization (parity-critical) ────────────────────────────────────

def _local_modified(raw: sqlite3.Row, tz, created_dt: datetime) -> datetime:
    """Site-local ``date_time_modified``, falling back to the created datetime.

    Cashew leaves the column NULL on transactions that were never edited, and older
    backups predate it entirely. Falling back to created keeps an unedited row's
    window behaviour byte-identical to before this field existed.
    """
    try:
        raw_modified = raw["date_time_modified"]
    except (IndexError, KeyError):
        return created_dt
    if raw_modified in (None, ""):
        return created_dt
    try:
        return datetime.fromtimestamp(int(raw_modified), tz=timezone.utc).astimezone(tz)
    except (TypeError, ValueError, OSError, OverflowError):
        return created_dt


def _normalize_row(
    raw: sqlite3.Row, company_currency: str, tz, lo: str | None, hi: str | None
) -> dict | None:
    """Map one SQLite row to the normalized dict. Returns ``None`` when the row's
    site-local date falls outside the requested inclusive window (caller skips it).
    ``lo``/``hi`` are ISO ``YYYY-MM-DD`` strings or ``None`` (no bound)."""
    # epoch (UTC seconds) → site-local datetime  ⚠ #1 parity trap
    local_dt = datetime.fromtimestamp(int(raw["date_created"]), tz=timezone.utc).astimezone(tz)
    local_date = local_dt.date()
    modified_dt = _local_modified(raw, tz, local_dt)

    # date-window filter on the SITE-LOCAL date (never an epoch-range SQL compare —
    # that risks an off-by-one at the tz boundary); ISO date strings sort correctly.
    #
    # The window is tested against the created date OR the modified date. Created
    # alone hides every EDIT to an older transaction: the edit does not move
    # date_created, so the row falls outside every window after the one that first
    # imported it and ERPNext keeps the pre-edit figure forever. That is exactly how
    # a loan edited from 150,000.00 down to 148,674.00 stayed at 150,000.00 in the
    # ledger. A row kept only because it was modified in-window still posts under its
    # real transaction date — see txn_date below, which stays on local_date.
    iso = local_date.isoformat()
    iso_modified = modified_dt.date().isoformat()
    created_in_window = not (lo and iso < lo) and not (hi and iso > hi)
    if lo and iso < lo and iso_modified < lo:
        return None
    if hi and iso > hi and iso_modified > hi:
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
        # Why this row survived the window. "modified" means its transaction date is
        # OUTSIDE the requested bounds and only the edit brought it back — such a row
        # is a revision of something already posted, never a new entry to create, or
        # an August import would silently write November entries into the ledger.
        # The idempotency guard enforces that; see apply_idempotency_guard.
        "_window_reason": "created" if created_in_window else "modified",
        # Persisted (no leading underscore, so api._dict_to_child copies them).
        # source_pk is stable across edits where source_hash is not; the pair is what
        # lets a re-import recognise an edited transaction instead of treating it as
        # new. Deliberately NOT part of _compute_hash — the hash must describe content
        # only, or a pk would make every row look unique and idempotency would break.
        "source_pk": raw["transaction_pk"],
        "source_modified": modified_dt.strftime("%Y-%m-%d %H:%M:%S"),
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


# ── budgets (f012 c012) — a SEPARATE path, deliberately not part of read_sqlite ─
#
# Budgets are reference data, not postings: they never become Cashew Import Row
# records, they touch no run counter, and a revert does not remove them. Keeping
# them out of read_sqlite is what guarantees that — the row pipeline literally
# cannot see them.
#
# The CSV export carries no budgets at all, so this is a SQLite-only capability.
# Both dashboard surfaces that consume budgets hide cleanly when there are none.

# Cashew's `budgets.reoccurrence` integer enum. FLAGGED ASSUMPTION (f012 D3.d /
# C5.5): every budget in every export observed so far is a (3, 1) default stamp,
# so no observation distinguishes the values — this is the declaration order of
# Cashew's own BudgetReoccurence enum, and 3 = Monthly is consistent with both
# live budgets being monthly. An unrecognised value RAISES; it is never bucketed
# as monthly, because a budget chart that is wrong but plausible is worse than
# no budget chart.
_REOCCURRENCE_LABELS = {
    0: "Custom",
    1: "Daily",
    2: "Weekly",
    3: "Monthly",
    4: "Yearly",
}

_BUDGET_SQL = """
SELECT budget_pk, name, amount, income, archived, pinned,
       start_date, reoccurrence, period_length,
       wallet_fks, category_fks, category_fks_exclude
FROM budgets
ORDER BY "order", budget_pk;
"""


def read_budgets(file_content: bytes) -> list[dict]:
    """Read the `budgets` table and return one dict per budget, PKs resolved to names.

    Name resolution happens HERE, not in the consumer, because the Cashew Account
    Mapping and Cashew Category Mapping tables key on the Cashew **name** — the
    CSV export carries no PKs, so names are the only identifier both ingestion
    paths share. A consumer holding raw `*_fk` strings has nothing to match on.

    Returns ``[]`` for a backup with no `budgets` table (older export) rather than
    failing — budgets are additive.

    Raises on an unrecognised `reoccurrence`. The caller is expected to treat that
    as "import no budgets this run", never as "import them as monthly".
    """
    tz = pytz.timezone(get_system_timezone() or _DEFAULT_TZ)
    return _with_ro_connection(file_content, lambda conn: _read_budgets(conn, tz))


def _read_budgets(conn: sqlite3.Connection, tz) -> list[dict]:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "budgets" not in tables:
        return []

    categories = _category_index(conn)
    wallets = {
        r["wallet_pk"]: (r["name"] or "").strip()
        for r in conn.execute("SELECT wallet_pk, name FROM wallets")
    }

    budgets = []
    for raw in conn.execute(_BUDGET_SQL):
        budgets.append({
            "budget_pk": raw["budget_pk"],
            "budget_name": (raw["name"] or "").strip(),
            "amount": float(raw["amount"] or 0.0),
            "is_income": 1 if int(raw["income"] or 0) == 1 else 0,
            "is_archived": 1 if int(raw["archived"] or 0) == 1 else 0,
            "is_pinned": 1 if int(raw["pinned"] or 0) == 1 else 0,
            # Epoch SECONDS in the site timezone. A UTC conversion moves the
            # anchor a day and shifts every cycle boundary after it.
            "start_date": _epoch_to_local_date(raw["start_date"], tz),
            "reoccurrence": _reoccurrence_label(raw["reoccurrence"], raw["budget_pk"]),
            "period_length": int(raw["period_length"] or 1) or 1,
            # `wallet_fks` is the wallet SCOPE; empty means ALL wallets. The
            # scalar `wallet_fk` column is a display anchor and takes no part in
            # matching — reading it as the scope changes real figures.
            "wallet_scope": [
                {"pk": pk, "wallet": wallets.get(pk)}
                for pk in _pk_list(raw["wallet_fks"])
            ],
            "category_scope": [
                {"pk": pk, **categories.get(pk, {"category": None, "sub_category": ""})}
                for pk in _pk_list(raw["category_fks"])
            ],
            "category_exclude": [
                {"pk": pk, **categories.get(pk, {"category": None, "sub_category": ""})}
                for pk in _pk_list(raw["category_fks_exclude"])
            ],
        })
    return budgets


def _category_index(conn: sqlite3.Connection) -> dict[str, dict]:
    """category_pk → ``{"category", "sub_category"}`` in Cashew Category Mapping's shape.

    Cashew nests one level: a row with `main_category_pk` set is a SUB-category,
    and the mapping table keys on the (parent name, own name) pair. A flat
    pk→name lookup would file every sub-category under a parent it does not have.
    """
    rows = {
        r["category_pk"]: ((r["name"] or "").strip(), r["main_category_pk"])
        for r in conn.execute("SELECT category_pk, name, main_category_pk FROM categories")
    }
    index: dict[str, dict] = {}
    for pk, (name, main_pk) in rows.items():
        if main_pk and main_pk in rows:
            index[pk] = {"category": rows[main_pk][0], "sub_category": name}
        else:
            index[pk] = {"category": name, "sub_category": ""}
    return index


def _pk_list(value) -> list[str]:
    """Parse a Cashew list column into opaque PK strings.

    Stored as a JSON array by Cashew's list converter; NULL and ``[]`` both mean
    "no restriction". Every element stays a STRING — seeded Cashew records use
    small integer PKs ("0" is Balance Correction, "5" is Entertainment), so a
    UUID parse or an int cast silently drops those legs.
    """
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v) != ""]
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        # Not JSON — fall back to a comma-separated list rather than dropping a scope.
        parsed = [p.strip() for p in str(value).split(",")]
    if not isinstance(parsed, list):
        return []
    return [str(v) for v in parsed if str(v) != ""]


def _epoch_to_local_date(value, tz) -> str | None:
    if value in (None, ""):
        return None
    try:
        return (
            datetime.fromtimestamp(int(value), tz=timezone.utc)
            .astimezone(tz)
            .date()
            .isoformat()
        )
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _reoccurrence_label(value, budget_pk: str) -> str:
    try:
        label = _REOCCURRENCE_LABELS.get(int(value))
    except (TypeError, ValueError):
        label = None
    if not label:
        frappe.throw(
            f"Budget {budget_pk} has an unrecognised reoccurrence value ({value!r}). "
            "Budgets were not imported. Report this value — the Cashew reoccurrence "
            "enum is only partially known, and guessing would misstate every cycle.",
            frappe.ValidationError,
            title="BUDGET_REOCCURRENCE_UNKNOWN",
        )
    return label


def _is_master_error(row: dict) -> bool:
    return row.get("validation_error_code") == "SQL_MASTER_UNRESOLVED"


def _clear_pairing_error(row: dict) -> None:
    """Reset a classifier transfer-pairing error (e.g. TRANSFER_PAIR_INCOMPLETE) to
    Valid, since the DB FK is the authoritative pairing signal. No-op otherwise."""
    if row.get("validation_status") == "Error" and not _is_master_error(row):
        row["validation_status"] = "Valid"
        row["validation_error_code"] = None
        row["validation_error_message"] = None
