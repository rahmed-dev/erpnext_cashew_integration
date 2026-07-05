# f011 — Cashew SQL Import: Dev Plan

Status: **COMPLETE & dev-ready** — architecture, seam, reuse contract, and the full
schema→field mapping (§5) are finalized against the real Cashew SQLite file
(`cashew-2026-07-04-…sql`, Drift schema v48). No open questions block dev.

---

## 0. One-paragraph summary for the developer

Cashew's import pipeline is format-agnostic. The only CSV-specific code is one line in
`api.parse_and_preview`. Your job is to add a **SQLite reader** that produces the exact
same list of normalized row dicts that `parser.parse_csv` produces, and branch to it at
that one seam based on a new `source_type` field on `Cashew Import Run`. If your row
dicts are correct, mapping, validation, idempotency, posting, diagnostics, and the SPA
all work unchanged. The single hard requirement is **`source_hash` parity**: the same
transaction read from CSV and from SQL must hash identically, or "add alongside" will
double-post.

---

## 1. The integration seam (verified in code)

`cashew_integration/api.py :: parse_and_preview(run_name)`:

```
122  file_content = _read_attached_file(run.source_file)
124  company_currency = ... Company.default_currency
127  rows = parse_csv(file_content, company_currency)   # <-- ONLY CSV-specific line
130  apply_mappings(rows, run)
132  run.set("import_rows", [])
133  for row in rows: child = run.append("import_rows", {}); _dict_to_child(row, child)
137  counters, period, status="Parsed", save, commit
```

`worker.process_run` (`worker.py:100`) later reloads rows **from the child table**, not
the file — so once your reader has persisted correct `Cashew Import Row` children,
100% of the rest of the pipeline is reused. **Do not touch** worker, posting, validation,
idempotency, diagnostics, mapping, or SPA.

### Change at the seam
Replace line 127 with a dispatch:

```python
if run.source_type == "SQLite":
    rows = read_sqlite(file_content, company_currency)   # new module
else:
    rows = parse_csv(file_content, company_currency)
```

`read_sqlite` returns the **same** `list[dict]` shape `parse_csv` returns (see §2).
Everything below line 127 (`apply_mappings` onward) is unchanged.

---

## 2. The output contract — normalized row dict

Your reader MUST emit, per transaction, a dict with these keys (source of truth:
`parser._parse_single_row`). Downstream depends on every one:

| key | type / shape | notes |
|---|---|---|
| `row_idx` | int, 1-based | stable ordering; used for transfer pairing + child key |
| `validation_status` | `"Valid"`/`"Error"`/`"Skipped"` | set `"Valid"` unless the row itself is bad |
| `validation_error_code` / `validation_error_message` | str/None | mirror `parser._error` on bad rows |
| `txn_date` | `"YYYY-MM-DD"` | **date only** (goes into hash) |
| `raw_txn_time` | `"HH:MM:SS"` | used for FX transfer-leg pairing (~1s apart) |
| `month_key` | `"YYYY-MM"` | item label + reporting |
| `raw_amount` | `round(abs(x), 2)` | positive magnitude |
| `category` / `sub_category` | str (NAME) | `sub_category` may be `""` |
| `raw_account` | str (Cashew account NAME) | goes into hash; drives Account Mapping |
| `title` / `note` | str | both go into hash; `note` drives transfer classification |
| `source_currency` | str code (e.g. `"PKR"`,`"USD"`) | goes into hash |
| `company_currency` | str | passed in |
| `income_flag` | **`"true"`/`"false"`** (lowercase strings) | goes into hash |
| `item_label` | `f"{category} | {month_key}"` | |
| `txn_type` | placeholder then set by `_assign_txn_type` | reuse the parser's helpers (§4) |
| `exchange_rate` / `base_amount` | `1.0`/`raw_amount` when `source_currency==company_currency`, else `None`/`0.0` | mapping fills the rest |
| `source_hash` | sha256 — see §3 | **must match CSV** |

**Reuse, don't reinvent:** import and call `parser._assign_txn_type`, `parser._classify_transfer_rows`, and (ideally) refactor `parser._compute_hash` into a shared helper both readers call. Do not re-implement transfer pairing.

---

## 3. `source_hash` parity — the one thing that must be exact

`parser._compute_hash` hashes this canonical JSON (sorted keys, `,`/`:` separators):

```json
{"account": raw_account, "amount": str(round(abs(full_precision_amount),10)),
 "currency": source_currency, "date": txn_date, "income": income_flag,
 "category": category, "subcategory": sub_category, "title": title, "note": note}
```

Rules for the SQLite reader:
- **`amount`** uses the **full-precision** float, not the 2dp `raw_amount`. Pull the raw
  numeric amount from the DB and pass it through the same `round(abs(x),10)` path. If
  Cashew stores signed amounts, take `abs`.
- **`account`, `category`, `subcategory`** are **NAMES**, not ids — JOIN to resolve.
- **`income`** must be the lowercase string `"true"`/`"false"` — map the DB bool/int.
- **`date`** is date-only ISO — derive from the DB timestamp (see §5 for its format).
- **`title`, `note`** verbatim as the CSV would carry them (see transfer-note caveat §5).

**Acceptance gate (c003):** golden test — take transactions that exist in BOTH a CSV
export and the SQLite file, run both readers, assert `source_hash` is identical per
transaction. Until this passes, add-alongside is unsafe.

**What the gate does and does NOT cover — read before trusting it:**
- The hash-parity test proves **dedup parity only** (per-row). It says *nothing* about
  transfer pairing or posting correctness — a mis-paired transfer still hashes fine.
- Add a **second assertion set** on posting: every internal Transfer JV balances (rate 1.0
  for same-currency legs; implied rate for FX), and each posted pair's two legs correspond
  to a `paired_transaction_fk` link (§5.5). This is the check that actually guards pairing.
- The test needs a CSV of the **same Cashew state** as the SQLite file. Dev must **export a
  CSV from the same DB** (Cashew Settings → Export) to run it — the provided `.sql` alone is
  not sufficient. If no matching CSV is available, the parity gate is unrunnable; say so and
  fall back to asserting the SQL reader's hashes against hand-computed expected values for a
  fixed sample.

---

## 4. Transfer / balance-correction handling

The parser's transfer logic (`_classify_transfer_rows`, `_pair_transfer_legs`) keys
entirely off:
- `category in {"Balance Correction","Balance Transfer"}`, and
- the `note` string matching `^Transferred Balance\n(.+) → (.+)$`, and
- `raw_txn_time` to pair FX legs.

Call the parser's existing functions on your rows — do **not** rewrite them. The only
risk is whether the DB gives you the same `note` string (see §5).

---

## 5. Schema Scan — COMPLETE (Cashew Drift schema, user_version 48)

Scanned `cashew-2026-07-04-...sql` (binary SQLite, 553 txns, 55 categories, 7 wallets).

### 5.1 Tables that matter
`transactions`, `categories`, `wallets`. (Others: `budgets`, `tags`,
`transaction_to_tag_links`, `objectives`, `delete_logs`, `app_settings`, … — not needed.)

### 5.2 Field mapping — SQLite → normalized row dict (§2)

| dict key | source | rule |
|---|---|---|
| `raw_account` | `wallets.name` via `transactions.wallet_fk` | `.strip()` (parser strips; matches CSV `account`) |
| `raw_amount` | `transactions.amount` (REAL, **signed**) | `round(abs(amount), 2)` |
| hash amount | same | `str(round(abs(amount), 10))` — full precision |
| `source_currency` | `wallets.currency` | **`.upper()`** ⚠ DB is lowercase `pkr`/`usd`; CSV is `PKR`/`USD` |
| `title` | `transactions.name` | `.strip()` (CSV `title`) |
| `note` | `transactions.note` | `.strip()`, keep interior `\n` (CSV `note`; transfer regex needs the newline) |
| `income_flag` | `transactions.income` (INT 0/1) | `"true"` if 1 else `"false"` |
| `category` | `categories.name` via `category_fk` | verbatim (CSV `category name`) |
| `sub_category` | `categories.name` via `sub_category_fk` | `""` when fk null (0 rows use it here) |
| `txn_date` / `raw_txn_time` | `transactions.date_created` (**Unix seconds**) | convert epoch → **site-local** datetime, then `.date()` / `.time()` ⚠ tz-critical |
| `month_key` | derived | `"%Y-%m"` of the local datetime |
| `source_hash` | all of the above | reuse `parser._compute_hash` unchanged |

### 5.3 Confirmed facts (no open questions remain)
- **Amount is signed:** `income=0 ⇒ amount<0` (452), `income=1 ⇒ amount≥0` (101). Take `abs`; derive direction from the `income` column, not the sign.
- **Transfer note IS STORED** in `transactions.note` as `"Transferred Balance\n{X} → {Y}"` — the parser regex matches it directly. **`c004` (note reconstruction) is NOT needed.** `paired_transaction_fk` is set on the source (negative) leg only, pointing to the dest `transaction_pk`; it is an *optional* robustness upgrade for pairing (see 5.5), not required.
- **Balance Correction** category exists (`category_pk='0'`, name `"Balance Correction"`); both `"Transferred Balance\n…"` (paired) and `"Updated Total Balance\n…"` (solo adjustment) note formats are present — matches the existing parser classification exactly.
- **Subcategories unused** in this dataset (`sub_category_fk` set on 0 rows) → `sub_category` is always `""`. Reader must still resolve it generally.

### 5.4 Row scope — the balance filter
- `paid`: **552 paid, 1 unpaid.** The single `paid=0` row is a future upcoming txn (`type=2`, dated 2026-07-13) that Cashew does NOT count toward current balance.
- **Filter: `WHERE paid = 1`.** Excludes unpaid upcoming/scheduled instances while keeping already-paid subscription/reoccurring instances (`type` 1/2 with `paid=1`), matching Cashew's displayed balance. Handled **by construction** — not presented as "the cause" of the original mismatch (one future-dated row is unlikely to explain a month's discrepancy, and we were asked not to investigate). It is simply the correct scope.
- `transactions` already excludes hard-deleted rows (`delete_logs` is a sync tombstone table, not a filter you apply).

### 5.5 Ordering & transfer pairing — FK is PRIMARY (this diverges from the CSV path)
- Assign `row_idx` over `ORDER BY date_created, transaction_pk` — deterministic, mirrors CSV chronology.
- **Pair transfers by `paired_transaction_fk`, not by note+time.** Rationale: the CSV
  path pairs source→dest by nearest `raw_txn_time` (never by amount — FX legs differ), and
  `date_created` is only second-resolution, so repeated same-note same-day transfers can
  *mis-pair silently* — and because transfer JVs balance "by construction" via the implied
  rate, a mis-pair posts a **balanced-but-wrong** JV that the hash-parity gate (per-row)
  can NOT catch. The DB gives us an authoritative link, so use it:
  - FK present **and resolves** to an in-file txn → internal transfer. Set
    `transfer_pair_row_idx` on both legs directly from the FK; stamp `txn_type="Transfer"`,
    `resolved_route="Transfer JV"`. (Scan: 30 of 31 resolve.)
  - FK present **but dangling** (partner not in file) → **External Transfer** (route
    `External Transfer JE`). Scan: exactly 1 — the `Saving → Meezan Bank` leg; `Meezan Bank`
    is the only note-partner that is not a Cashew wallet.
  - FK **absent** on a `Transferred Balance` leg with no partner pointing at it → treat as
    External / incomplete via the existing classifier fallback.
- **Consequence to state for dev:** for the SQL path, pairing becomes part of the reader
  (it sets `transfer_pair_row_idx` up front). You may still call
  `parser._classify_transfer_rows` for the note-parsing + external/adjustment routing, but
  the *pairing* decision is FK-driven, not time-driven. This is a deliberate divergence
  from the "reader is the only new code" story — call it out in the spec.
- Scan sanity (already run): 0 transfer groups with >2 legs sharing one second, 0 `paid=1`
  orphans, 31 FKs (1 dangling), note-partners all wallets except `Meezan Bank`.

### 5.6 Timezone (must-get-right for hash parity)
`date_created` is **UTC Unix seconds**; Cashew's CSV exports **device-local** time. Example: `1738708920` = `2025-02-04 22:42 UTC` = **Feb 5** in PKT (UTC+5). Convert with the **Frappe site timezone** (`System Settings.time_zone`, expected `Asia/Karachi`) before extracting the date, or `txn_date` — a hash field — drifts by one day and every cross-source hash for late-night txns diverges. The golden parity test (§3) is the guardrail; if it fails on a subset of rows, timezone is the cause.

### 5.7 Reader SQL (starting point)
**Use LEFT JOIN for wallet + category, never INNER.** An inner join silently drops any
`paid=1` row whose wallet/category was deleted — re-creating the exact omission bug we are
fixing. (Scan: 0 such orphans today, but the reader must not depend on that.) When a
master does not resolve, emit an **error row** (`validation_status="Error"`,
code `SQL_MASTER_UNRESOLVED`) — surfaced in diagnostics — not a dropped row.

```sql
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
```
Per row: **`.strip()` `account`, `title`, `note`** exactly as the parser does (else trailing
whitespace breaks hash parity), `.upper()` currency, epoch→**site-tz** datetime, `abs`+round
amount, income→`"true"/"false"`, and if `account`/`category` is NULL emit the error row above.
Then over the full list: set `transfer_pair_row_idx` from `paired_transaction_fk` (§5.5),
run the parser's `_assign_txn_type` + `_classify_transfer_rows` (for routing/note parsing),
and the shared `_compute_hash`.

---

## 6. Data model changes

- Add `source_type` (Select: `CSV` / `SQLite`, default `CSV`) to **Cashew Import Run**.
  Drives the §1 branch and lets the SPA/Desk show which path a run used.
- Accept `.sql`/`.sqlite`/`.db` uploads on the run's `source_file` (attach validation).
- No other schema change — `Cashew Import Row` is reused as-is.

---

## 7. Build order (suggested)

1. `source_type` (Select CSV/SQLite) field on Cashew Import Run + `.sql/.sqlite/.db`
   attach-type allowance (`c002`).
2. Refactor `parser._compute_hash` into a shared helper both readers call (parity insurance).
3. Write `importer/sqlite_reader.py :: read_sqlite(file_content, company_currency)` using
   §5 (SQL in §5.7, mapping in §5.2, filter §5.4, tz §5.6). Emit §2 dicts; then call
   `parser._assign_txn_type` + `parser._classify_transfer_rows` over the list (`c001`).
4. Branch `parse_and_preview` on `source_type` (§1). `apply_mappings` onward unchanged.
5. Golden parity test CSV vs SQLite (`c003`) — **gate**: same txns, identical `source_hash`.
6. End-to-end: import the real SQLite file into a scratch company; compare computed
   per-wallet balances against Cashew's in-app balances (sanity, not a diff-investigation).

**Dropped from original scope:** `c004` (transfer-note reconstruction) — not needed; the
note is stored verbatim in the DB (§5.3).

---

## 8. Out of scope

- Diagnosing the original CSV/Cashew mismatch (user declined).
- Automated live sync from Cashew (that is f002).
- Any change to posting, validation, mapping, revert, diagnostics, or the SPA.
