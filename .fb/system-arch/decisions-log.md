## Primary User and Access Model — 2026-04-08
**Decision:** Primary user is Accountant, and implementation should follow standard ERPNext permission system.
**Rationale:** Import operation is finance-owned; standard ERPNext roles and permission behavior are sufficient without custom permission architecture.

## Posting Targets by Transaction Type — 2026-04-08
**Decision:** Income transactions post to Sales Invoice. Expense transactions post to Purchase Invoice when amount is above a configurable threshold; below threshold, post as Journal Entry.
**Rationale:** This keeps accounting treatment aligned with business rules while allowing operational flexibility through a configurable cutoff amount.

## Idempotency and Duplicate Handling — 2026-04-08
**Decision:** Cashew transaction uniqueness must be enforced on ERP side so the same source transaction cannot be posted twice, even though Cashew CSV is expected to have no internal duplicates.
**Rationale:** Cashew CSV lacks a stable ID and is considered duplicate-free at export time, but re-import/retry safety is still required in ERPNext.

## Validation Behavior — 2026-04-08
**Decision:** Rows with errors are blocked from posting.
**Rationale:** Prevents invalid accounting entries and ensures only validated transactions are posted.

## Import Diagnostics and Auditability — 2026-04-08
**Decision:** Persist import runs in an Import Log DocType and provide downloadable CSV diagnostics.
**Rationale:** Supports accountant troubleshooting, audit traceability, and operational follow-up after each run.

## Processing Model — 2026-04-08
**Decision:** Use background job queue with status polling for import execution.
**Rationale:** Expected file volume and posting workload can exceed request-time limits; async processing improves reliability and user experience.

## Future Integration Direction — 2026-04-08
**Decision:** Architect for CSV now with API transport later.
**Rationale:** Delivers immediate value while preserving an upgrade path to automated Cashew sync once API channel details are confirmed.

## Expected Volume — 2026-04-08
**Decision:** Design for approximately 100-1000 rows per import file.
**Rationale:** This range informs queue-first processing, progress reporting, and batch-safe validation/posting behavior.

## Category-to-Account Strategy — 2026-04-08
**Decision:** Use default mapping from a finance-managed mapping table, with accountant override at preview before import.
**Rationale:** Mapping table keeps governance and maintainability, while preview override handles edge cases without blocking operations or requiring immediate mapping-table changes.

## Per-Row Party Resolution (No CSV Editing) — 2026-04-08
**Decision:** Customer/supplier must be resolved per SI/PI row without requiring manual CSV edits:
- First: mapping rules (account/title/category/note patterns),
- Then: deterministic extraction from `title`/`note` where possible,
- Finally: accountant preview override for unresolved rows.
Rows missing required party after this pipeline are blocked from posting.
**Rationale:** Cashew export does not carry guaranteed ERP party fields; ERP posting still requires party context. Per-row resolution preserves accounting correctness without forcing users to modify source files.

## Cash-Basis Source to Accrual ERP Posting — 2026-04-08
**Decision:** Treat Cashew data as cash evidence but post in ERPNext as accrual-compliant accounting documents:
- `posting_date` reflects transaction/economic date from Cashew.
- `auto_settle_cash` defaults to **true** — a Payment Entry is created automatically for every SI and PI at import time, because Cashew records actual cash events and there is no pending receivable or payable.
- Threshold-based routing (Sales Invoice / Purchase Invoice / Journal Entry) remains, but every path must preserve clear audit linkage to source row.
**Rationale:** Cashew is a cash-basis personal finance app; every recorded transaction is already settled. Creating invoices without immediately settling them would leave false open AR/AP balances. Auto-settling at import time keeps aging reports accurate by construction.

## Multi-Currency Handling (PKR/USD) — 2026-04-08
**Decision:** f001 supports multi-currency import for at least PKR and USD rows within the same file.
- Keep source row currency on posted documents where supported.
- Resolve exchange rate by transaction date (ERP rate source, with preview override when missing).
- Persist both source amount and company-currency base amount on import rows for audit and reconciliation.
**Rationale:** Cashew exports currently include more than one currency; forcing pre-conversion or manual CSV edits would break the direct-import objective and increase accounting risk.

## Exchange Rate Source of Truth — 2026-04-08
**Decision:** The actual transacted exchange rate — not the ERP rate table — is the authoritative source for all foreign-currency rows.
- For **Transfer pairs (Balance Correction)**: the implied rate is computed directly from the pair's actual amounts (e.g., `PKR received / USD sent`). No ERP rate lookup is performed; the pair amounts are the ground truth.
- For **all other foreign-currency rows (SI/PI/JE)**: the ERP rate table is used as a **convenience default only** — it pre-fills the `exchange_rate` field in the preview UI. The accountant always has the opportunity to override it with the actual transacted rate.
- If the ERP rate is absent for a given currency/date: the row enters preview with `exchange_rate = null`; the accountant must fill in the actual rate before queueing. A null rate at queue time is a hard block.
- `EXCHANGE_RATE_MISSING` is therefore a **queue-time validation gate**, not a pre-preview block.
**Rationale:** ERP rate tables hold system-configured reference rates that may not match the actual rates at which transactions occurred (e.g., bank conversion rate at time of USD receipt). Posting at the actual transacted rate produces accurate base-currency amounts and avoids FX discrepancies that would otherwise surface as reconciliation noise. The preview step is the natural place for the accountant to confirm or correct the rate for each foreign-currency row.

## Balance Correction / Transfer Row Handling — 2026-04-08
**Decision:** Rows with `category name == "Balance Correction"` represent internal account-to-account transfers and must be posted as Transfer Journal Entries — not skipped, and not routed through the SI/PI/JE expense-income pipeline.
- Transfer rows come in pairs (source leg: income=false, destination leg: income=true) sharing an identical note in the format `Transferred Balance\n{source} → {destination}`.
- Each valid pair produces one Journal Entry: Debit destination ERPNext account, Credit source ERPNext account.
- Cross-currency transfers (e.g., USD → PKR) use the **implied exchange rate** derived from the pair's actual amounts rather than the ERP rate table, so the JV balances in company currency by construction.
- Pairs that cannot be matched (count ≠ 2 for a given note, or unparseable note) are blocked as validation errors.
**Rationale:** Skipping transfer rows would produce an incorrect balance picture — the real cash movement between accounts must be recorded. Using the implied rate eliminates dependency on a potentially absent ERP rate for the transfer date while keeping the books balanced.

## Cashew Account Mapping — 2026-04-08
**Decision:** Add a `Cashew Account Mapping` configuration DocType that maps each Cashew account name (from the CSV `account` column, e.g., "Petty Cash", "NSave", "Saving") to an ERPNext GL account.
- This mapping is required for every row; missing mapping is a hard validation error.
- Used as the cash source/destination leg in JE and Transfer JV posting.
- Stored on every import row for audit linkage.
**Rationale:** The CSV `account` column carries real cash account identity. JE and Transfer JV posting cannot proceed without knowing which ERPNext GL account corresponds to each Cashew account; a single run-level field would be insufficient for files containing rows across multiple Cashew accounts.

## Configuration Structure — 2026-04-08
**Decision:** All configuration (Account Mapping and Category Mapping) lives in a single `Cashew Settings` singleton document with two child tables. No separate standalone DocTypes for config. No `company` field on config rows — company scoping is handled solely by `Cashew Import Run.company`.
**Rationale:** Simpler to maintain (one place for all config), avoids duplicating company on every mapping row when a single-company setup is the target, and reduces DocType sprawl.

## Party Resolution — 2026-04-08
**Decision:** Remove `Cashew Party Mapping Rule` DocType. Party resolution uses two stages only: (1) per-row preview override by the accountant, (2) `default_customer` / `default_supplier` fields on the run as fallback. No automatic rule-based matching.
**Rationale:** No transactions in the current CSV dataset have title/note fields that reliably identify ERP party masters. Rule-based matching adds complexity without delivering value at this stage. A run-level default party covers the common case (all freelance income to one customer, all expenses to one supplier) with zero config overhead.

## Balance Correction Classification — 2026-04-08
**Decision:** Rows with category `"Balance Correction"` **or** `"Balance Transfer"` are treated identically as transfer/adjustment candidates and classified into four subtypes at parse time:
1. **Paired internal transfer** ("Transferred Balance\nX → Y" with both legs in file) → Transfer JV
2. **External-account orphan** ("Transferred Balance\nX → Y" with partner not in file) → External Transfer JE; requires partner account in Cashew Account Mapping
3. **Solo adjustment** (all other Balance Correction rows: "Updated Total Balance", no note, etc.) → Skipped-Adjustment by default; optionally Adjustment JE if `run.post_adjustments = 1`
**Pairing key:** Group by (note, txn_date_day) — not note alone — to correctly separate identical-note transfers on different dates.
**Rationale:** Skipping all Balance Correction would produce incorrect balances. Pairing by note+date resolves the repeated-note problem (e.g., "Petty Cash → Saving" appears across many dates). External orphans are real cash movements that must be recorded. Solo adjustments always post as Adjustment JEs — manual review via the review_recommended flag in diagnostics, not by skipping the posting.

## Solo Adjustment Posting — 2026-04-08
**Decision:** Solo Balance Correction / Balance Transfer rows (non-paired) always post as Adjustment Journal Entries against a configurable `balance_adjustment_account` on the run. No opt-in toggle. If the file contains adjustment rows and `balance_adjustment_account` is not set, the queue is blocked with `RUN_CONFIG_MISSING`.
**Rationale:** Zero-touch import requires every row to be handled automatically. Skipping adjustment rows would leave real cash events unrecorded and require manual follow-up after every import. Auto-posting to a suspense/equity account keeps the books complete while the review_recommended flag in diagnostics signals rows that warrant accountant attention.

## SQL (SQLite) Import — Second Ingestion Path — 2026-07-04 (f011)
**Decision:** Add a Cashew SQLite ("SQL file") import path **alongside** the CSV import
(f001), not replacing it. Implemented as a new reader module (`sqlite_reader.py`) that
emits the **same normalized row-dict** `parser.parse_csv` emits, branched at the single
CSV-specific seam — `api.parse_and_preview` (`api.py:127`) — by a new `source_type` field
on `Cashew Import Run`. All downstream stages (mapping, validation, idempotency, worker,
posting, diagnostics, SPA) are format-agnostic and reused unchanged (verified:
`worker.process_run` reloads rows from the child table, never re-parses).
**Crux:** `source_hash` parity — the SQLite reader must denormalize FKs to names and
normalize types to the exact CSV string shapes (account/category/subcategory NAMES,
currency code, `income` as `"true"`/`"false"`, date-only `txn_date`, full-precision
amount) so the same transaction from CSV and SQL dedupes to one posting via the existing
idempotency guard. Enforced by a golden CSV-vs-SQLite hash-parity test.
**Precondition (assumption, per user — no investigation):** the current CSV/Cashew balance
mismatch is assumed to be OMISSION (CSV dropped rows). If CSV instead posted wrong values,
add-alongside double-counts and the prior CSV run must be reverted (f004).
**Rationale:** Smallest change that meets the goal — one contained module + one branch,
reusing the entire posting pipeline; keeps CSV as fallback and enables cross-source diffing.
**Status:** Plan drafted (`features/f011-cashew-sql-import/arch/sql-import-plan.md`).
BLOCKED on the actual `.sql` file for the schema→field mapping (esp. whether the transfer
note string is stored or exporter-synthesized).

## Charting Engine — Apache ECharts — 2026-08-07 (f012)
**Decision:** The SPA's charting engine is **Apache ECharts** (via `vue-echarts`),
replacing ApexCharts. `apexcharts` / `vue3-apexcharts` are removed once the existing
`IncomeExpenseChart.vue` is ported; two engines must not ship simultaneously past the port.
All charts go through one shared `<CsChart>` wrapper (theme, palette, currency and tooltip
formatting, empty/loading state, resize); tree-shaken `echarts/core` imports only, never the
full bundle — the SPA is PWA-precached, so payload is a real cost.
**Rationale:** user asked for a standout analytics UI. ECharts' financial-analytics chart
types (calendar heatmap, sankey, sunburst, gauge) have no ApexCharts equivalent of comparable
quality, and paying the port cost once beats carrying two engines.
**Supersedes:** f010 Decision 9's steer "no Apache ECharts unless TD has a strong reason".
The reason is now recorded at architecture level, not deferred to TD.
**Detail:** `features/f012-dashboard-analytics/arch/decisions.md` → Decision 1.

## Dashboard Time-Series Aggregates — 2026-08-07 (f012)
**Decision:** `api.dashboard_summary` is extended with period-bucketed time-series —
monthly (and daily for short periods) income/expense, per-category series over time, and
account balance history — additively, keeping every existing key's name and meaning.
Bucketing is site-timezone aware (same tz discipline as f011 c001) and computed with grouped
SQL, not a per-bucket loop. Rule 4 of the SPA API discipline still binds: one aggregate
endpoint per surface, `ignore_permissions=False` internally, `has_permission` gates at entry.
Chart-slice drill-down into transaction lists remains **out of scope** (as in f010 D9).
**Rationale:** trend, calendar-heatmap, flow, and period-over-period charts are impossible
against the current single-period response shape. This is the half of the work that raises
the ceiling; the engine swap is the other half.
**Detail:** `features/f012-dashboard-analytics/arch/decisions.md` → Decision 2.

## Chart Colour — Curated Categorical Ramp — 2026-08-07 (f012)
**Decision:** Multi-series and categorical charts use one curated, contrast-checked
categorical ramp (~8–10 hues) defined in a single module and consumed by `<CsChart>`.
The Cashew accent stays the primary/emphasis colour (single-series charts, highlights,
selection, hover). Income / expense / transfer carry fixed semantic colours that do not
change hue between charts.
**Rationale:** deriving 8+ hues from one accent by rotation or lightness reliably yields
muddy or contrast-failing adjacent categories — precisely the "looks cheap" outcome f012
exists to fix. A curated ramp is predictable and testable.
**Amends** `design-philosophy.md` point 6 (accent-only colour): charts are the one narrow
exception, and the ramp module is the only sanctioned non-accent colour source.
**Detail:** `features/f012-dashboard-analytics/arch/decisions.md` → Decision 4.

## SQLite Becomes the Default Import Path — 2026-08-07 (f011 p004)
**Decision:** `Cashew Import Run.source_type` defaults to **SQLite**, not CSV. The SPA
upload surface opens on the SQLite toggle, and the dropzone's default accept list is
`.sql / .sqlite / .db`. **CSV is retained as a fully supported option** — this flips the
default, it does not remove a path.
**Rationale:** the SQLite backup is Cashew's own source of truth and demonstrably the better
import. The CSV export is a derived, flattened view that has already caused a real incident
(the balance mismatch f011 was built to fix — CSV silently omitted rows). The SQL reader also
carries data the CSV has no column for at all: FK-authoritative transfer pairing
(`paired_transaction_fk`), stable `transaction_pk`/`budget_pk` UUIDs, and the `budgets` and
`objectives` tables. Defaulting to the weaker format invited the omission bug every time.
**Consequences:**
- `source_type` field `default` flips CSV → SQLite; existing runs are unaffected because the
  value is stored per run.
- The `import_from_date` / `import_to_date` window fields — `depends_on
  source_type=='SQLite'` — are now visible by default. A blank window still means the whole
  backup, so the default behaviour is unchanged.
- SPA `UploadSection.vue` segmented toggle and `CsvDropzone.vue` accept list default to the
  SQL path (f011 c005).
- Goals and spending limits (f012 c012 / c013) exist only on the SQL path, so this makes
  them reachable by default rather than opt-in.
- Docs and the setup wizard should describe SQL as the normal path and CSV as the fallback.
**Detail:** `features/f011-cashew-sql-import/feature.yaml` → patch p004.

### f012 Goals live in `budgets`, not `objectives` — 2026-08-07
Scanning the real 2026-07-04 export settled where Cashew keeps the user's goals: the
**`budgets`** table, not `objectives`. Two live rows — **Savings 50,000/month** (`income=1`,
wallet `Saving`, categories Savings + Balance Correction) and **Food outdoor 10,000/month**
(`income=0`, wallet `Petty Cash`, category Entertainment), both pinned, unarchived, monthly
(`reoccurrence=3`, `period_length=1`). `objectives` holds only two zero-amount **loan**
trackers and `transactions.objective_fk` is non-null on zero rows.
**Decision:** import `budgets` into a new `Cashew Budget` doctype keyed on `budget_pk`;
the `income` flag selects the treatment — `1` is a savings goal (gauge), `0` is a spending
limit (budget-vs-actual, new component c013, inverted colour semantics since exceeding a
limit is bad). Matching = category_fks ∩ wallet_fks ∩ direction, both resolved through the
EXISTING Category and Account Mappings, so no new config surface.
**TRAP:** both live budgets carry an `end_date` in Aug 2025. `start_date` is the recurrence
anchor and `end_date` ends the FIRST period only — deriving the window from `end_date` marks
every recurring budget expired. Use `start_date` + reoccurrence; `archived` is the real
inactive signal.
**Unblocks** the goal work that D3.a-bis had parked pending a fresh export.
**Detail:** `features/f012-dashboard-analytics/arch/decisions.md` → D3.a-ter.

### f012 Budget cycle + rendering rule — 2026-08-07 (D3.d)
**Decision:** the budget's own row is authoritative for its period — store `reoccurrence`
and `period_length`, map `{0 custom, 1 daily, 2 weekly, 3 monthly, 4 yearly}` × period_length,
and derive every window from `start_date` + those. No period setting in ERPNext.
**Rendering follows the filter:** more than one cycle in the selected period → per-cycle marks
against the limit line (savings = per-cycle series, spending limit = per-cycle bars coloured
over/under); one cycle or less → gauge for savings, single bar for a limit. Never pro-rate —
a pro-rated recurring budget is a number that exists nowhere in Cashew.
**UNVERIFIED, flagged:** the 2026-07-04 export cannot validate the enum. Every transaction and
both budgets carry the identical `reoccurrence=3, period_length=1`, including one-off paid
rows, so `3/1` is Cashew's default stamp, not evidence. **An unrecognised value must RAISE at
import, never silently fall back to monthly** — a wrong cycle misstates every budget figure.
**Knock-on:** cycle bucketing uses the budget's own anchor and cycle, not the dashboard's
month buckets (a weekly budget over a 3-month filter yields ~13 marks), so c002's time-series
needs daily granularity as the floor. A partial trailing cycle is shown and marked partial.
**Detail:** `features/f012-dashboard-analytics/arch/decisions.md` → D3.d.

### f012 Follow-ups — RESOLVED — 2026-08-07
- **Savings gauge = goal, not rate.** New DocType field `Cashew Settings.savings_target_amount`
  (Currency, per-month, no default). The gauge plots `income − expense` against it, pro-rated by
  months in the selected period, and hides entirely when the target is unset. Chosen over a
  percentage savings-rate because an amount is concrete and checkable; a rate moves with income.
- **Expense breakdown = treemap, not sunburst.** f011's scan found `sub_category_fk` unused on
  every row, so the category dimension is flat and a sunburst would degenerate into the donut the
  dashboard already shows. Data contract stays hierarchy-ready (optional `children`) so the swap
  is later a one-component change.
- **Invoice KPI card** = volume and value of SI/PI posted in the period, not outstanding AR/AP
  (`auto_settle_cash` defaults true, so open AR/AP is empty by construction).

## Cashew Schema Facts — Budgets, PKs, Dates — 2026-08-07 (f012 coherence pass)

Established by scanning `cashew-2026-08-07-00-20-33-593933.sql` (652
transactions). These are properties of the Cashew schema, not of f012, and bind
on any future code that reads a Cashew backup.

- **Primary keys are opaque strings, not UUIDs.** `categories.category_pk` and
  `wallets.wallet_pk` are TEXT, and Cashew's seeded defaults use small integer
  strings — category `"0"` is Balance Correction, `"5"` is Entertainment, wallet
  `"0"` is Investment. Live user data references them. Never validate a Cashew
  FK against a UUID pattern and never coerce one; a `uuid.UUID()` parse drops
  real rows silently.
- **`budgets` date columns are Unix epoch seconds**, not ISO strings. Convert in
  the site timezone, same discipline as f011 c001 — a UTC conversion moves an
  anchor to the previous day and shifts every derived cycle boundary.
- **A budget's account scope is `wallet_fks`, not the scalar `wallet_fk`.**
  NULL or `[]` in `wallet_fks` means all wallets; the scalar is a display and
  currency anchor that takes no part in matching. Reading the scalar as the
  scope changed one real budget's monthly figure by 2,256.
- **`budgets.start_date` is the recurrence anchor; `end_date` ends the first
  period only.** Both of the user's live budgets carry an August 2025 end_date.
  Deriving an active window from `end_date` marks every recurring budget
  expired. `archived` is the real inactive signal.
- **`budgets.reoccurrence` cannot be validated from any export.** Every
  transaction and every budget in both the July and August exports carries the
  identical `(reoccurrence 3, period_length 1)`, including one-off paid rows
  that do not recur — so `3/1` is a default stamp, not evidence. The assumed
  mapping is `{0 custom, 1 daily, 2 weekly, 3 monthly, 4 yearly}`. Any code
  decoding it must **raise on an unrecognised value rather than default to
  monthly**: a wrong cycle silently misstates every budget figure downstream.
- **`budgets.budget_transaction_filters` is undocumented** (`[6]` and `[5]` on
  the two live rows) and is deliberately ignored. First suspect if an ERP budget
  figure ever disagrees with what Cashew shows on screen.

### f011 Schema Scan — RESOLVED — 2026-07-04
Scanned the real Cashew SQLite file (Drift schema v48, 553 txns). Plan §5 is dev-ready.
Key parity rules locked: currency `.upper()` (DB lowercase vs CSV uppercase); epoch→site-tz
before date (UTC seconds vs CSV local); amount signed → abs + direction from `income` col;
transfer note stored verbatim (c004 dropped); row-scope filter `WHERE paid=1` (excludes the
1 upcoming/unpaid txn — the likely original mismatch cause). Stage → arch-done.
