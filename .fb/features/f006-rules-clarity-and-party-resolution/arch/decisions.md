# f006 — Architecture Decisions

Feature: Rules Clarity & Party Resolution v2
Owner: bmad-fb-architect
Status: in-progress (decisions being recorded as user confirms)

---

## Decision 1 — Loan modeling via `category_type` on Cashew Category Mapping (2026-05-03)

**Decision:** Add a `category_type` Select field to Cashew Category Mapping with four options:

```
category_type = Income | Expense | Loan Out | Loan In
```

The combination of `category_type` + per-row `income_flag` (CSV direction) determines posting route:

| category_type | income_flag | Semantic | Posting |
|---|---|---|---|
| Income | true | Income | Existing income JE / SI |
| Expense | false | Expense | Existing expense JE / PI |
| Loan Out | false | Lent (you lend) | DR Loan Receivable, CR Cash; party=Customer on receivable line |
| Loan Out | true | Loan Repayment Received | DR Cash, CR Loan Receivable; party=Customer on receivable line |
| Loan In | true | Borrowed (you borrow) | DR Cash, CR Loan Payable; party=Supplier on payable line |
| Loan In | false | Loan Payment Made | DR Loan Payable, CR Cash; party=Supplier on payable line |

**Rationale:**
- Loans are balance-sheet accruals, not P&L. They must hit a party-tracked receivable/payable account, not income/expense + party hack on JE.
- 4-option enum (vs user's original 6-option proposal: lent/borrowed/loan_paid/loan_payment_received) avoids redundancy: direction is already in the CSV; encoding direction twice (once in category_type, once in income_flag) creates mapping ambiguity (e.g. user picks wrong category_type for a refund / reversal row).
- Existing Income / Expense behavior unchanged — additive change, no migration of past Cashew Import Row records.

**Implications:**
- New `txn_type` enum value(s) needed on Cashew Import Row. Likely **two**: `Loan Receivable` and `Loan Payable` (parser sets based on category_type + direction), OR a single `Loan` value with sub-route on `resolved_route`. TD to pick the cleaner shape.
- New `resolved_route` enum values: `Loan Receivable JE`, `Loan Payable JE` (or equivalent).
- New posting handler module (parallel to existing `posting.py` routes). Handler must:
  - Resolve target Loan Receivable / Loan Payable account (decision pending — see Decision 4 below).
  - Place party + party_type on the receivable/payable GL line, not the cash line.
  - Honor existing rounding tolerance + multi-currency rules from f001.
- `requires_party` flag on Cashew Category Mapping is now redundant for Loan rows (Loan Out always requires Customer; Loan In always requires Supplier). For Income/Expense, flag keeps existing meaning.
- Backwards compatibility: existing Cashew Category Mapping rows default `category_type = Income` if `income_flag` was income, else `Expense` (additive migration).

**Open within this decision:**
- D1.a: Single `Loan` txn_type with sub-route, vs two distinct txn_types `Loan Receivable` / `Loan Payable`. **Defer to TD.**

---

## Decision 2 — Drop rule-based party resolution; party is per-row manual (2026-05-03)

**Decision:**
- No automatic party resolution rules. No per-category default party, no per-account default party, no counterpart-text matching, no rule precedence chain.
- Party is set **manually per row** in the Vue Row Explorer (Decision 3) before posting.
- Engine validates `party present when required` and accepts whatever is set.
- Run-level `default_customer` / `default_supplier` fields on Cashew Import Run: **DROP**. Migration: keep columns nullable for old runs (backwards compat for f004 revert paths); remove from form layout; mapping engine ignores them.
- Resolution trace persistence: **DROP**. No rules → nothing to trace. (See Decision 3 — history panel also dropped.)

**Rationale:**
- User confirmed Cashew CSV carries no usable party signal. Notes / titles are not maintained.
- Rules add engine complexity, fixture maintenance, and a rules-dashboard UI that delivers near-zero value when every party still ends up needing manual confirmation.
- Pain is not "the engine guesses wrong"; pain is "setting party on N rows is tedious". Decision 3 (Vue Explorer with bulk + inline edit) addresses this directly.

**Parked future idea — Prefill From Prior Import:**
User raised: match incoming row to a similar row from a prior posted import (same category + raw_account + similar amount?) and suggest its party. Promising but **out of f006 scope**. Needs its own architecture pass — similarity heuristic, suggestion vs auto-fill, audit, opt-in toggle. Captured in `parked.md` as f-future candidate.

**Stale system-arch decision check:**
- `data-flow.md` "Party Resolution — 2026-04-08" already states "no rule-based matching" — stays valid.
- `data-flow.md` "Per-Row Party Resolution (No CSV Editing) — 2026-04-08" pipeline (mapping rules → extraction → preview override) collapses to **per-row manual set only**. Cascade: revise wording in `data-flow.md` after f006 dev pass; no spec churn needed yet (only f001 specs reference the old pipeline and that code stays as-is — Loan path bypasses it, Income/Expense path keeps it but with rules disabled).

---

## Decision 3 — Vue Row Explorer as primary investigation + fix surface (2026-05-03)

**Decision:** Build a Frappe **Page** (Desk-native) named `cashew-row-explorer` mounted at `/app/cashew-row-explorer/<run-name>`. Vue-based. Loads all Cashew Import Rows of the selected Cashew Import Run.

Capabilities:
- Filter by category, raw_account, txn_type, category_type, validation_status, posted state.
- Column presets: Compact, Resolution, Validation, Posted, Loans-and-Parties.
- Inline party set / change per row (writes back to Cashew Import Row via whitelisted API).
- "Resolve validation conflict" action per row → modal listing failing field(s) (party, account, etc.) with save button. Re-runs validation on save.
- Status pills with color (Valid / Error / Skipped / Posted / Reverted).
- Search across raw text, category, party.
- Bulk action: select N rows, set party (or party_type) on all in one shot.

Run form change: drop heavy in-Run child-table grid as primary surface. Replace with compact summary + "Open in Row Explorer" button. Rows still exist as Cashew Import Row records — Vue page is just a richer view over them.

**Dropped:** "Explain this row" trace panel. No rules → no trace. No history panel either (kept simple per user direction).

**Rationale:**
- Frappe Page (vs `www/` route): keeps Desk chrome, workspace listing, native permission attach, single-app navigation. Accountants stay in one UI.
- Vue (vs Script Report): only path that delivers inline edit + modal-fix flow. Script Report cannot mutate rows.
- Compact summary on Run form (vs delete grid entirely): preserves quick at-a-glance status without forcing a page switch.

**Trade-off accepted:**
- Build cost vs Script Report: real but justified — fix-from-here is the core UX win of f006.
- Frappe Page vs Vue SPA app: lighter scope, integrates with bench build pipeline already in use for Frappe.

**Open within this decision:**
- D3.a: Whitelisted API surface (single fat endpoint vs per-action endpoints) — defer to TD.
- D3.b: Realtime / polling for status updates while a Run is processing — defer to TD.

---

## Decision 4 — Loan account selection: shared accounts with party tracking (2026-05-03)

**Decision:** Two shared balance-sheet accounts in the chart, both party-tracked at the GL line level:
- **Loan Receivable** (Asset) — used by every `category_type = Loan Out` row. Party_type=Customer.
- **Loan Payable** (Liability) — used by every `category_type = Loan In` row. Party_type=Supplier.

Each Cashew Category Mapping with `category_type = Loan Out` sets its `default_account` to the Loan Receivable account; `Loan In` mappings set it to Loan Payable. Existing `default_account` Link field on Cashew Category Mapping carries this — no schema addition needed beyond `category_type` itself.

Per-borrower / per-lender balances surface via standard ERPNext party-wise reports (Accounts Receivable Summary, Accounts Payable Summary, party ledger) over those two accounts.

**Rejected: per-party dedicated account** (e.g. `Loan Receivable - John`).
- Bloats chart of accounts on every new loan counterparty.
- Same per-party visibility already available from party reports on the shared account — no real upside.
- Adds setup friction (new account per borrower before posting).

**Rationale (shared + party):**
- ERPNext-native pattern. Party tracking on receivable/payable accounts is the framework's intended use.
- Aligns with how trade receivables / payables are already handled in standard ERPNext.
- Keeps chart small and reports clean; party filter handles the per-counterparty story.

**Implications:**
- Setup wizard / install fixtures should ensure Loan Receivable + Loan Payable accounts exist (or guide user to create them and bind to a Loan-type category).
- Posting handler must enforce: every Loan-route GL line on the receivable/payable side carries `party_type` + `party`. Validation blocks posting otherwise.
- Cashew Category Mapping JSON gains `category_type` (Decision 1) but `default_account` field semantics are stable — TD specs of f001 unchanged.

---

## Decision 5 — Validation error UX (2026-05-03)

**Decision:**
- Validation error message text **always prefixed with `[Row {row_idx}]`** in `validation_error_message` so messages remain useful when copied or surfaced outside the grid (logs, diagnostics CSV, hover, modal).
- Vue Row Explorer's filter "Errors only" + click-to-fix modal replaces in-grid Small Text truncation as primary error-handling surface.
- `validation_error_code` field already exists — Vue page maps codes to friendly labels + drives which fix-action modal opens (party-missing → party picker, account-missing → account picker, etc.).
- Diagnostics CSV (`Cashew Import Run.diagnostics_file`) — confirm during dev pass that it carries row_idx + validation messages; if not, extend it.

**Rationale:** Cheapest possible improvement to the immediate pain. Message-prefix change is a single edit in `validation.py`. Vue modal handles richer cases.
