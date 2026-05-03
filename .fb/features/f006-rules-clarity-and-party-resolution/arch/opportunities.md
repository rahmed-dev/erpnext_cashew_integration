# f006 — Codebase Improvement Opportunities

Status: discovery scan, **not** decisions. Architect to convert chosen items into entries in `decisions.md` after user discussion.

Date: 2026-05-03
Scope: cashew_integration app code (`/home/riz/work-bench/apps/cashew_integration`)
Themes (user ask): **Loans**, **Party Resolution**, **UX**.

---

## A. Loans — current support: none

**A1. `txn_type` enum has no Loan.**
File: `cashew_import_row.json` → `txn_type` options = `Income\nExpense\nTransfer\nExternal Transfer\nAdjustment`.
Loan flows currently fall into Income or Expense and post via SI/PI/JE — wrong account, wrong party semantics.

**A2. `resolved_route` enum has no Loan route.**
Options: `Journal Entry\nTransfer JV\nExternal Transfer JE\nAdjustment JE`. Loan disbursement / repayment / interest cannot route to a distinct posting path.

**A3. Loan categories seeded but inert.**
`setup.py:37,62` seeds categories `"Loan Payment Received"` and `"Lent"`, but parser (`parser.py:187-193`) treats them as Income/Expense based purely on `income_flag`. The seed implies loan intent; the engine ignores it.

**A4. No party_type switching by category.**
Loans need party=Customer for "Lent" (borrower owes you) but direction is Expense in Cashew. Engine's run-default chain (`mapping.py:407-414`) hardwires `Income → Customer`, `Expense → Supplier`. Loan party assignment impossible without override per row.

**Decision needed:** Loan as new `txn_type` (parser-detected from reserved names) **vs** category `kind` attribute (Income/Expense/Loan/Transfer/Adjustment) on Cashew Category Mapping driving route + party_type.

---

## B. Party Resolution — current support: shallow

**B1. Resolution chain has 2 stages only.** (mapping.py:`_resolve_party`)
```
preview override (per row) → run default (by income/expense direction)
```
No per-category party. No per-account party. No counterpart-text matching. Decisions log (2026-04-08 "Party Resolution") explicitly removed `Cashew Party Mapping Rule` doctype as "no value at this stage" — that decision is now stale per user real-world experience and **must be revised**.

**B2. `Cashew Category Mapping` has no party fields.** Only: cashew_category, cashew_sub_category, default_account, requires_party, is_active. Cannot bind a category to a default party / party_type.

**B3. `Cashew Account Mapping` has no party fields.** Only: cashew_account_name, erp_account, account_currency, is_active. Cannot bind an account (e.g. "NSave") to a default party.

**B4. `requires_party` is binary, party_type is implicit.** Engine infers party_type from txn_type direction. No way to say "this category requires a Customer even though it's an Expense" → blocks loans + reverse-direction commissions, refunds, owner draws.

**B5. CSV counterpart hints unused.** title / note columns parsed but never consulted for party resolution. Lowest-cost rule type to add.

**B6. `party_source` field is single-string ("Run Default" / "Preview Override").** No structured trace of which rule was considered, which fired, which fell through. User cannot answer "why this party?".

**Decision needed:**
- Schema shape: extend `Cashew Category Mapping` with party fields **vs** introduce `Cashew Party Rule` top-level doctype.
- Precedence chain: per-row override → per-account default → per-category default → counterpart-text rule → run default by direction (suggested order).
- Resolution trace: persist JSON on row (durable, survives revert) **vs** compute on-demand (cheaper, drifts).

---

## C. UX — current state: dense form, zero client customization

**C1. `Cashew Import Row` child grid floods.** Counted ~17 `in_list_view: 1` fields out of 38 total. Grid scrolls horizontally; user cannot scan a 500-row run.

Fields currently in grid: raw_account, txn_date, raw_amount, source_currency, company_currency, exchange_rate, base_amount, txn_type, category, resolved_route, resolved_account, resolved_erp_account, resolved_party, validation_status, validation_error_message, posted_doctype + ~1 more. Mixes parse / resolve / validate / post columns into one wall.

**C2. No client scripts / list view JS.** No `public/js/*` assets shipped (only nexus_erp boilerplate in hooks). No way to:
- toggle column presets (Compact / Resolution / Validation / Posted / Loans-and-Parties)
- color-code status pills
- expand long error messages
- "Explain this row" side panel

**C3. No reports.** `report/` dir empty. Frappe Report Builder not used → no pre-built diagnostic views.

**C4. No workspace customization.** No accountant landing page; user opens Import Run by direct nav.

**C5. `validation_error_message` is Small Text in grid.** Long messages truncate awkwardly; no hover-expand.

**C6. Run-level config buried on the Run form.** `default_customer`, `default_supplier`, `balance_adjustment_account`, `je_rounding_tolerance` set per-run — repetitive. Should default from Cashew Settings, override per run.

**C7. No bulk per-row party override.** Engine supports preview override but UI requires editing rows one-by-one; no filter+set action on the Run grid.

**C8. No re-run-mapping action.** After editing Cashew Settings, user must re-import the CSV to re-resolve. Should be re-map only (skip parse).

**Decision needed:**
- Row Explorer surface: Frappe Script Report (cheap, preset-friendly) **vs** Vue page on Cashew workspace (flexible, build cost).
- Whether C6/C7/C8 land in f006 scope or split to a follow-up "Operator Quality of Life" feature.

---

## D. Cross-cutting / out-of-theme but adjacent

**D1. Configuration Structure decision (system-arch) constrains us.**
Decisions log (2026-04-08): "All config in Cashew Settings singleton, two child tables, no standalone DocTypes." If we go with a third doctype (Cashew Party Rule), this decision needs revision with cascade plan to TD specs of f001.

**D2. No fixtures for category/account mapping templates.** Each new install starts blank (apart from setup.py seed of category names). User onboarding pain.

**D3. `Cashew Import Run.diagnostics_file`** exists but unclear if it surfaces resolution explanations or only validation errors. Worth confirming as candidate carrier for a "rule trace" CSV per run.

**D4. No `bench_path` / `apps_path` / `frappe_version` in `_bmad/config.toml`.** Architect / TD / Dev rely on these for shell ops. Suggest user run `bmad-fb-setup`.

---

## Suggested grouping for component breakdown (TD's job, not architect's — listed for visibility)

1. Schema migration — new fields on Category Mapping + Account Mapping; possibly `kind` on Category Mapping; possibly new `Cashew Party Rule` doctype.
2. Mapping engine v2 — new precedence chain, counterpart-text matcher, structured resolution_trace.
3. Loan posting route — new txn_type + resolved_route + posting handler.
4. List view UX — client script for column presets, status pills, expand-on-hover.
5. Row Explorer report (or Vue page) — preset views.
6. Rules dashboard on Cashew Settings — precedence diagram + hit counts.
7. Bulk per-row party override action.
8. Re-map action (without re-parse).
9. Backwards-compat — additive fields, existing rows keep working, f004 revert paths intact.

---

## Open questions inherited from f006 stub (still open)

- Loan as new `txn_type` (parser-detects reserved names) **or** category `kind` attribute?
- Counterpart rules on Category Mapping child table **or** separate `Cashew Counterpart Rule` doctype?
- Resolution trace: persisted JSON on row **or** computed on-demand?
- Row Explorer: Script Report **or** Vue page?
