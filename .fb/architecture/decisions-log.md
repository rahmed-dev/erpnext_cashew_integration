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
