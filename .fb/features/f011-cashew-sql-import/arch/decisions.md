# f011 Cashew SQL Import — Architecture Decisions

## Ingestion Strategy — Add Alongside CSV — 2026-07-04
**Decision:** SQL (SQLite) import is a **second ingestion path** added alongside the
existing CSV import (f001). The CSV parser (`c002` of f001) is retained, not retired.
**Rationale:** User chose to keep CSV as a fallback and to allow diffing the two
sources. Cost is one more reader to maintain; benefit is a safe fallback and the
ability to cross-check SQL output against CSV output.

## Reuse the Entire Pipeline — Only the Reader Is New — 2026-07-04
**Decision:** The import pipeline is format-agnostic downstream of parsing. The single
CSV-specific seam is `api.parse_and_preview`, which calls `parser.parse_csv(file_content,
company_currency)` and then `apply_mappings(...)` before persisting `Cashew Import Row`
child docs. Everything after — mappings, validation, idempotency guard, async worker,
posting engine (SI/PI/JE/Transfer JV/External Transfer/Adjustment), diagnostics CSV, and
the SPA — reads persisted child rows and is reused with **zero change**. SQL import adds
one module (`sqlite_reader.py`) that emits the **same normalized row-dict schema**
`parse_csv` emits, selected at the seam by a `source_type` discriminator.
**Rationale:** Smallest change that meets the requirement (Architect decision order:
config → scripting → app code; here it is a contained new module + one branch). Avoids
re-implementing mapping/validation/posting. Keeps a single source of truth for how a
Cashew transaction becomes ERP documents.
**Verified in code:** `worker.process_run` reloads rows from the child table
(`worker.py:100`), never re-parses — confirming the pipeline consumes persisted rows, not
the file. `parse_and_preview` (`api.py:100-156`) is the only `parse_csv` call site.

## source_hash Parity Is the Correctness Crux — 2026-07-04
**Decision:** The SQLite reader MUST reproduce the exact flattened string values the CSV
`source_hash` is built from, so the same transaction ingested from CSV and from SQL
produces an **identical** `source_hash` and the existing idempotency guard collapses them
to one posting. The hash payload (`parser._compute_hash`) is:
`account` (Cashew account NAME string), `amount` (`str(round(abs(x),10))`), `currency`
(code string), `date` (`txn_date`, **date only**), `income` (`"true"`/`"false"`),
`category` (NAME), `subcategory` (NAME), `title`, `note`.
**Implication for the reader:** Cashew's DB almost certainly stores FKs (wallet id,
category id) and typed columns (bool income, signed amount, epoch/ISO datetime). The
reader must **denormalize FKs to names** and **normalize types to the CSV's string
shapes** — otherwise "add alongside" double-posts every shared transaction.
**Rationale:** Add-alongside only stays safe if cross-source dedup holds. This is the one
requirement that, if missed, silently corrupts the books.

## Precondition: Discrepancy Assumed to Be Omission — 2026-07-04
**Decision (assumption, not an investigation):** Per user instruction the CSV/Cashew
balance mismatch is **not** being diagnosed. The SQL approach is safe **only if** the
mismatch was CSV *omitting* rows. If CSV instead imported rows with *wrong values*, the
SQL run posts correct rows under new hashes while the wrong CSV postings remain → double
counting. If that turns out to be the case, the prior CSV run must be reverted (f004)
before or after the SQL run.
**Rationale:** Records the safety boundary of the chosen approach without reopening the
investigation the user declined.

## Schema→Field Mapping — RESOLVED via scan — 2026-07-04
Scanned the real Cashew SQLite file (`cashew-2026-07-04-…sql`, Drift schema v48, 553 txns).
Full mapping in `sql-import-plan.md` §5. Decisions that came out of the scan:

- **Transfer note is stored verbatim** in `transactions.note` → the parser regex works
  directly; **`c004` (note reconstruction) is dropped.** `paired_transaction_fk` (on the
  source leg) is available as an optional stronger pairing key but is not required.
- **Currency parity:** wallet currency is lowercase (`pkr`/`usd`) in the DB but the CSV
  exports uppercase (`PKR`/`USD`, confirmed via `tests/test_mapping.py` fixtures). The
  reader MUST `.upper()` currency, else every cross-source `source_hash` diverges.
- **Timezone parity:** `date_created` is UTC Unix **seconds**; the CSV exports device-local
  time. The reader MUST convert epoch → **site timezone** (`Asia/Karachi`) before taking
  the date, or `txn_date` (a hash field) drifts a day for late-night txns.
- **Amount:** REAL and **signed** (income=0 ⇒ negative). Take `abs`; derive direction from
  the `income` column, not the sign.
- **Row scope:** filter `WHERE paid = 1`. Excludes the single unpaid/upcoming future txn
  (`type=2`, 2026-07-13) that Cashew does not count toward balance — this is the most
  likely source of the original CSV/Cashew mismatch, now handled by construction.

The plan (`sql-import-plan.md`) is dev-ready with no open questions.

## Transfer Pairing by `paired_transaction_fk` (SQL path diverges) — 2026-07-04
**Decision:** On the SQL path, pair transfer legs by the DB's `paired_transaction_fk`, NOT
by the CSV path's note+time heuristic. The reader sets `transfer_pair_row_idx` from the FK
before handing rows to `_classify_transfer_rows` (which still does note parsing + external/
adjustment routing). FK dangling (partner not in file) → External Transfer.
**Rationale:** The CSV pairing keys off `raw_txn_time` at second-resolution and never off
amount (FX legs differ), so repeated same-note same-day transfers can mis-pair. Because a
transfer JV balances "by construction" via the implied rate, a mis-pair posts a
balanced-but-WRONG JV that the per-row hash-parity gate cannot detect. The DB link is
authoritative (31 present, 30 resolve, 1 dangling = the one external `Meezan Bank` transfer).
**Trade-off accepted:** this makes pairing part of the SQL reader — a deliberate, documented
divergence from the "reader is the only new code" story. Posting/routing stay shared.

## LEFT JOIN + Error Row, Never Silent Drop — 2026-07-04
**Decision:** The reader query uses LEFT JOIN for wallet and category; a `paid=1` row whose
master doesn't resolve becomes a validation **error row** (`SQL_MASTER_UNRESOLVED`), surfaced
in diagnostics — never silently dropped.
**Rationale:** An INNER JOIN would silently omit rows referencing deleted masters — the exact
omission failure this feature exists to fix. (Scan: 0 orphans today, but the reader must not
rely on that.)

## Import Scope — User-Chosen Date Window (not full-DB auto) — 2026-07-04 (TD)
**Decision:** The `.sql` is the whole Cashew DB (all history), but the pipeline never
filters by period — `_compute_txn_period` (api.py:159) only *derives* period_start/end from
`min/max` of the imported rows. So the SQL reader must decide scope explicitly. Chosen:
**user-chosen date window.** Add optional `import_from_date` / `import_to_date` (Date) to
`Cashew Import Run` (SQLite-only, `depends_on eval source_type=='SQLite'`); `read_sqlite`
takes `from_date`/`to_date` and keeps rows whose **site-local** txn date is inside the
inclusive window.
**Rationale:** Lets the user import "just this month" rather than replaying all 553 txns
every run. Both bounds optional → blank/blank = whole DB, so the full-backfill path is still
available for free.
**Implementation constraints (spec'd in c001/c002):** filter on the **site-local** date
(same tz conversion as `txn_date`), NOT the raw UTC epoch — an epoch-range SQL comparison
risks an off-by-one-day at the Asia/Karachi boundary. Guard `from_date > to_date`. Empty
window = valid empty run. Idempotency still dedupes within/across runs, so overlapping
windows are safe.
**Options considered:** (A) full-DB + hash-dedupe [rejected: no per-run control]; (B) user
date window [CHOSEN]; (C) pre-scan months then pick [rejected: extra endpoint + UI for
little gain over B].

## SPA SQLite Upload Surface — in scope (c005) — 2026-07-04 (TD)
**Decision:** The SQL path is usable from the `/cashew` SPA, not Desk-form only. c002 adds the
doctype fields + seam dispatch but the f010 SPA upload flow (`run-workspace/upload/`) is
hardwired to CSV (`CsvDropzone` accept + copy, `UploadSection` form field list + "CSV parsed"
toast). New component **c005** extends `UploadSection.vue` + `CsvDropzone.vue` with a
CSV/SQLite toggle, the optional date-window inputs, `.sql/.sqlite/.db` acceptance, and threads
`source_type`/`import_from_date`/`import_to_date` through run create + field-persist. Secondary:
a `source_type` badge on the run list/header.
**Rationale:** Without it, the operator-facing surface (SPA, from f010) can't drive the feature —
they'd have to drop to the Desk form. The SPA already owns run creation + upload, so this is the
natural home. Stays additive: default `source_type=CSV` keeps today's SPA flow byte-identical.
**API discipline (app CLAUDE.md):** writes keep the existing `frappe.client.insert` /
`set_value` + `parse_and_preview` path (new fields are plain doc fields — no new endpoint);
reads add `source_type` to the existing `get_list` fields; controls use frappe-ui, not native.
**Depends on c002** (fields + dispatch must exist first). depends_on: [c002].

## Gate Scope — hash parity ≠ pairing/posting — 2026-07-04
**Decision:** The golden hash-parity test proves dedup parity only. A second assertion set
must cover posting: internal Transfer JVs balance (rate 1.0 same-currency; implied FX) and
each posted pair matches a `paired_transaction_fk` link. The parity test also requires a CSV
exported from the *same* Cashew state as the `.sql`; if unavailable, assert SQL hashes
against hand-computed expected values for a fixed sample.
**Rationale:** Prevents "gate is green" from being mistaken for "transfers post correctly."
