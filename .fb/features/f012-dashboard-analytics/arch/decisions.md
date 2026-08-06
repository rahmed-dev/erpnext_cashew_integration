# f012 — Dashboard Analytics & Charts — Architecture Decisions

Feature goal: turn the SPA finance dashboard (`/cashew`, f010 c007) from a
mostly-tiles surface with a single chart into a real analytics view with a
rich, deliberately-designed chart set.

## Starting state (surveyed 2026-08-07)

- `frontend/src/pages/FinanceDashboard.vue` (190 lines) + 12 components under
  `frontend/src/components/finance-dashboard/`.
- Exactly **one** chart today: `IncomeExpenseChart.vue` (239 lines), built on
  **ApexCharts** (`apexcharts ^4.7.0` + `vue3-apexcharts 1.8`, both already in
  `frontend/package.json`). Everything else is tiles (`BalanceTile`,
  `BalanceTileGrid`), lists (`CategoryBreakdownList`, `AssetBreakdownCard`),
  and chrome (`PeriodSelector`, `CompanySelector`, `RecentImportsStrip`).
- `cashew_integration.api.dashboard_summary` (api.py:930) returns single-period
  aggregates only: `income_total`, `expense_total`, `income_by_account`,
  `expense_by_account`, `assets_by_account`, `balance_tiles`, `recent_runs`,
  `currency`, `period`, `company`. **No time-series of any kind.**
- f010 Decision 9 deferred the charting-library choice to TD with the steer
  "lightweight — no dashboarding framework (no Apache ECharts unless TD has a
  strong reason)". ApexCharts was the resulting TD pick.

Framing given to the user before deciding: the dashboard does not read as flat
because of the library. It reads flat because there is one chart and the data
behind it is a single-period aggregate. A library swap alone buys a small
fraction of the desired outcome; the rest comes from time-series data and a
deliberate chart design system.

---

## Decision 1 — Swap the charting engine to Apache ECharts (2026-08-07)

**Decision:** Replace ApexCharts with **Apache ECharts** via the `vue-echarts`
Vue 3 wrapper as the single charting engine for the SPA. ApexCharts and
`vue3-apexcharts` are removed from `package.json` once
`IncomeExpenseChart.vue` is ported; **two chart engines must not ship
simultaneously past the port.**

**Options presented:**

| Option | Day-to-day | Cost | Enables |
|---|---|---|---|
| A. Keep ApexCharts + add a theme layer | Zero migration, already shipping | Default aesthetic is generic without a shared theme config | donut / bar / area / heatmap / treemap / radial / sparkline |
| **B. Swap to Apache ECharts (chosen)** | Rewrite `IncomeExpenseChart`, imperative option-object API | ~150–200 KB gz tree-shaken; reverses f010 D9's steer | sankey, sunburst, calendar heatmap, gauge, themeRiver, rich transitions |
| C. Unovis (`@unovis/vue`) | Cleanest minimal aesthetic, Vue-3-native composables | Full rewrite; smaller catalog and community | modern minimal analytics set |
| D. ECharts for new charts, keep Apex for the old one | No port needed up front | Two engines in the bundle — maintenance smell | same as B |

**Rationale (user decision):** the user asked explicitly for an
analytics/charts library with a standout UI. ECharts is where that lives for
financial analytics — its calendar heatmap (spend density by day), sankey
(money flow between accounts and categories), sunburst (category →
subcategory drill), and gauge have no ApexCharts equivalent of comparable
quality. Option D was rejected in the same breath as B was chosen: paying the
port cost once is cheaper than carrying two engines.

**This explicitly supersedes f010 Decision 9's "no Apache ECharts unless TD
has a strong reason".** The strong reason is recorded here: chart-type
coverage the product now requires, chosen by the user at architecture level
rather than by TD at spec level.

**Binding constraints for TD / Dev:**
- Use **tree-shaken imports** (`echarts/core` + explicit chart and component
  registrations), never `import * from 'echarts'` — the full bundle roughly
  doubles the SPA payload and the SPA is PWA-precached (c014), so bundle size
  is a real cost, not a theoretical one.
- Every chart goes through **one shared wrapper component** (working name
  `<CsChart>`) that owns theme, palette, tooltip formatting, currency
  formatting, empty state, loading state, and responsive resize. No page
  builds an ECharts option object inline.
- The SPA design philosophy (`.fb/system-arch/design-philosophy.md`) still
  binds. Two points bite here: accent colour comes only from
  `var(--cs-accent*)` / the `cs.accent` Tailwind colour, never a hardcoded
  hex; and ECharts tooltips render into their own DOM layer, so they must sit
  in the **z-50 overlay band** — not above it.

**Open for TD:** whether `vue-echarts` (the wrapper) is used or a thin
in-house `<CsChart>` calling `echarts.init` directly. Lean is `vue-echarts`
for the resize/lifecycle handling, wrapped by `<CsChart>` so the dependency is
swappable behind one file.

---

## Decision 2 — Extend `dashboard_summary` with time-series data (2026-08-07)

**Decision:** Extend the backend so the dashboard has real time-series to draw.
`dashboard_summary` gains period-bucketed aggregates — at minimum monthly (and
daily where the selected period is short enough to justify it) income and
expense series, per-category series over time, and account balance history
across the period.

**Options presented:** (a) extend the endpoint with time-series, (b)
frontend-only prettier renderings of today's numbers, (c) time-series **plus**
click-a-slice drill-down to a filtered transaction list.

**Chosen: (a).** Drill-down (c) was **not** selected — f010 Decision 9 listed
"drill from chart slices into transaction lists" as out of scope for v1 and
that remains true. Charts in f012 are read-only views.

**Rationale:** trend lines, calendar heatmaps, sankey flow, and any
period-over-period comparison are impossible against the current response
shape. This is the half of the work that actually raises the ceiling; the
engine swap is the other half.

**Binding constraints for TD / Dev:**
- Rule 4 of the SPA API discipline still binds (CLAUDE.md, f010 D5): aggregates
  live in **one purpose-built endpoint per surface**, and internal reads use
  `frappe.get_all(... ignore_permissions=False)` so row-level permissions still
  apply during aggregation. Time-series extends `dashboard_summary`; it does
  not spawn one endpoint per chart.
- The existing entry gates (`frappe.has_permission` on `GL Entry`, `Account`,
  `Company`) stay, and any new doctype touched gets the same treatment.
- Bucketing must be **site-timezone aware**, consistent with the tz handling
  f011 c001 established for the SQLite reader — a GL posting date bucketed in
  UTC would land some transactions in the wrong month.
- The endpoint is already the dashboard's single round-trip; adding series must
  not turn one query into N. Expect grouped SQL (`GROUP BY` on a period
  expression), not a per-bucket loop.
- Response shape is additive — existing keys keep their names and meanings so
  the current tiles and `IncomeExpenseChart` port cleanly.

**Open for TD:** bucket-granularity rule (fixed monthly vs. adaptive
daily/weekly/monthly by period length), and whether balance history is
computed from running GL sums or from period-end snapshots.

---

## Decision 3 — Chart inventory for v1 (2026-08-07)

**Decision:** The v1 dashboard carries seven charts plus a KPI card row.

**Core set (all four selected):**

1. **Income vs Expense trend** — monthly stacked bars (income up, expense down)
   with a net line overlay. Replaces today's single-period `IncomeExpenseChart`;
   this is the workhorse and the one the ApexCharts port collapses into.
2. **Net worth / balance history** — area or line of total assets across the
   period.
3. **Expense sunburst** — category → subcategory rings, click to zoom a ring.
   Source: the Cashew category/subcategory dimension already carried on rows,
   mapped through `Cashew Category Mapping`.
4. **Calendar heatmap** — one cell per day, colour by that day's spend.

**Advanced set (three of four selected):**

5. **Sankey money flow** — income sources → accounts → expense categories.
   Highest visual impact and the heaviest backend work; TD should treat it as
   the component most likely to need its own aggregation shape.
6. **Savings-rate gauge** — `(income − expense) / income` for the period.
   **Needs a target to be meaningful** — see open question below.
7. **Account balance stacked area** — one band per cash account over time, so
   the mix shift between Petty Cash / Saving / bank is visible.

**Not in v1:** "Top categories with period-over-period delta" was offered and
not selected. Parked, not rejected — it is the cheapest remaining win if the
dashboard later needs a compact comparison surface.

**KPI card row (added by the user):** a card row including **total expense**
and **invoice** figures for the selected period.

- *Assumption recorded, flagged to the user:* "invoice" is read as **volume and
  value of Sales Invoices and Purchase Invoices posted in the period**, not
  outstanding AR/AP. Rationale for the reading: the system-arch decision
  "Cash-Basis Source to Accrual ERP Posting" sets `auto_settle_cash` to true by
  default, so every SI/PI is settled at import time and open AR/AP is empty by
  construction — an outstanding-balance card would read zero on a healthy
  system. If outstanding balances were what was meant, this decision needs
  revising before TD.
- The card row reuses / extends the existing `BalanceTile` +
  `BalanceTileGrid` components rather than introducing a parallel card system.

**Layout guidance for UI/TD:** this is a lot of surface for one page. The
mobile-responsive constraint from f010 D2.c still binds — seven charts must
degrade to a single readable column on a phone, not a scaled-down desktop grid.
UI phase should decide whether the dashboard splits into sections (Overview /
Trends / Flow) or stays one long scroll before component specs are written.

### D3.a — Savings gauge measures a fixed amount goal, not a rate (resolved 2026-08-07)

**Decision:** The gauge is a **savings goal** gauge, not a savings-rate gauge.
It plots actual savings (`income − expense` for the period) against a **fixed
target amount** configured by the user, in company currency.

- New field **`Cashew Settings.savings_target_amount`** (Currency). This is a
  DocType change and gets its own component (c012).
- The target is defined as a **per-month** amount. The dashboard period is
  user-selectable and often is not one month, so the gauge **pro-rates**: the
  effective target is `savings_target_amount × months_in_selected_period`. The
  gauge subtitle must state the pro-rated figure so the number is never
  ambiguous ("PKR 90,000 target — 3 months × 30,000").
- When `savings_target_amount` is unset or zero, the gauge **hides entirely**
  rather than rendering an empty or infinite dial. It must not show a zero
  target.
- Over-achievement is shown, not clipped — a period at 140% of goal reads 140%.

**Rationale (user decision):** asked whether the gauge was a savings goal, the
user chose a fixed amount over a percentage rate. An amount is concrete and
directly checkable against a bank balance; a rate is a derived ratio that moves
when income moves, which makes it a poor thing to aim at.

**Naming consequence:** component c009 is the **savings-goal gauge**, not the
"savings-rate gauge". Renamed in `feature.yaml`.

### D3.a-bis — Goals are IMPORTED from Cashew, not configured in ERPNext (revised 2026-08-07)

**This supersedes the `Cashew Settings.savings_target_amount` field above.**
That field is **not built**; c012 is re-scoped accordingly.

**Decision:** goal definitions come from **Cashew's own Goals feature**, read out
of the `objectives` table during SQLite import and stored in ERPNext as a
doctype the gauge reads. The user already maintains goals in Cashew and does not
want to maintain a second copy. Progress is measured against a **designated
account**, matching how Cashew itself scopes an objective (`objectives.wallet_fk`).

**Schema scan of the real export** (`cashew-2026-07-04-18-03-44-147880.sql`,
Drift v48, performed 2026-08-07 — this decision is grounded in the actual file,
not the Cashew docs):

`objectives` table columns: `objective_pk`, `type`, `name`, `amount`, `order`,
`colour`, `date_created`, `end_date`, `date_time_modified`, `icon_name`,
`emoji_icon_name`, `income`, `pinned`, `archived`, `wallet_fk`.

`transactions` carries **two** objective links: `objective_fk` (savings-goal
link) and `objective_loan_fk` (loan link).

What the July export actually contains — **2 rows, both loans, no savings goals:**

| name | type | amount | wallet_fk → | end_date |
|---|---|---|---|---|
| Haider | 1 | **0.0** | NSave | null |
| General loan | 1 | **0.0** | Saving | set |

- `type: 1` is Cashew's **loan** objective. A savings goal is `type: 0`.
- `objective_fk` on `transactions`: **0 non-null rows**. `objective_loan_fk`: 5.
- Both objectives have `amount = 0.0` — no target to draw a gauge against.

**Conclusion: as of 2026-07-04 there were no savings goals in the data, only two
loan trackers.** The goals the user tracks were created after that export.

**Status: BLOCKED on a fresh Cashew export.** The user is producing one. Until a
backup containing `type: 0` objectives with non-zero `amount` is scanned, the
following are unverified and must not be guessed at:

- G1 — that `type: 0` is in fact the goal discriminator (inferred from the
  loan rows being `type: 1`; not yet observed directly).
- G2 — whether goal **progress** is derived by summing transactions whose
  `objective_fk` matches, or by reading the linked wallet's balance, or both.
  This determines whether the ERP-side gauge sums GL postings or reads an
  account balance.
- G3 — the meaning of `income` on an objective row (1 on both loan rows).
- G4 — how `archived` and `pinned` should map to visibility on the dashboard.
- G5 — whether `end_date` is a deadline to render on the gauge or advisory.

**Known asymmetry, accepted:** the **Cashew CSV export carries no objectives at
all**. Goals therefore exist only on the SQLite import path (f011). A
CSV-only user sees no gauge. That is acceptable — SQL is the go-forward path —
but it must be stated in the docs, and the gauge must hide cleanly rather than
error when no goals have ever been imported.

**Shape (provisional, to be confirmed after the fresh scan):**
- New doctype **`Cashew Goal`**, keyed on `objective_pk` (a stable UUID, same
  idempotency principle f002 D9 established for `transaction_pk`).
- Fields: `objective_pk`, `goal_name`, `target_amount`, `cashew_wallet`,
  `erp_account` (resolved through the existing `Cashew Account Mapping` by
  wallet name — reuses the mapping already in place, no new config surface),
  `end_date`, `is_archived`, `objective_type`.
- Import is **upsert on `objective_pk`**, run as part of the SQLite import.
  A goal deleted in Cashew does not vanish from ERPNext — matching f002 D9's
  insert-only stance on deletions.
- The gauge shows **pinned, non-archived goals with a non-zero target**.
  Everything else is filtered out, which correctly renders today's two
  zero-amount loan objectives invisible.

### D3.a-ter — Goals live in `budgets`, not `objectives`. UNBLOCKED (2026-08-07)

**User was right, and this supersedes D3.a-bis's blocked status.** The goal the
user tracks is a Cashew **Budget**, not an objective. c012 is no longer blocked
and no fresh export is needed.

**`budgets` table, scanned in the same 2026-07-04 file — 2 rows, both real:**

| name | amount | `income` | scope | pinned / archived |
|---|---|---|---|---|
| **Savings** | 50,000 | **1** | wallet `Saving`; categories `Savings`, `Balance Correction` | 1 / 0 |
| **Food outdoor** | 10,000 | **0** | wallet `Petty Cash`; category `Entertainment` | 1 / 0 |

Both `period_length: 1`, `reoccurrence: 3` (= monthly),
`is_absolute_spending_limit: 0`, `added_transactions_only: 0`.

Actuals computed from the same file to prove the matching rule works —
Savings: Feb 60,000 · Mar 40,000 · Apr 160,000 · Jun 40,000.
Food outdoor: Apr 22,110 · May 32,689 · Jun 32,355 · Jul 4,970 against a 10,000
limit, i.e. blown roughly 3× every month.

**Decision: import `budgets`, and let `income` select the treatment.**

- **`income = 1` → a savings goal.** Renders as the c009 gauge. This is the
  user's "measure against a certain account" — the budget already carries
  `wallet_fk` / `wallet_fks`.
- **`income = 0` → a spending limit.** Renders as budget-vs-actual (new
  component c013), not a gauge. A spending limit and a savings target are
  opposite in meaning: exceeding a savings goal is good, exceeding a spending
  limit is bad, and the colour treatment must invert accordingly.

**Matching rule** (verified against the data, reproduced in
`demo/aggregate_from_backup.py`): a transaction counts toward a budget when its
`category_fk` is in `category_fks` (empty means all), its `wallet_fk` is in
`wallet_fks` (empty means all), and its `income` flag equals the budget's. On
the ERP side both dimensions resolve through the mappings that already exist —
`Cashew Category Mapping` and `Cashew Account Mapping` — so no new config
surface appears.

**TRAP, must be handled in the importer:** both budgets carry an `end_date` in
**August 2025**, and both are live. `start_date` is the recurrence **anchor**
and `end_date` is the end of the **first** period only. Deriving the current
window from `end_date` marks every recurring budget expired. Compute the active
window from `start_date` + `reoccurrence` + `period_length` against the
dashboard period instead. `archived` is the real "not active" signal.

**Consequences for earlier decisions:**
- c012 is re-scoped from `Cashew Goal` to **`Cashew Budget`**, keyed on
  `budget_pk`, and is **unblocked**.
- The `objectives` path is dropped from f012 entirely. It stays relevant to
  f008 only, for the loan link below.
- G1–G5 in D3.a-bis are moot — they asked about a table that turned out to be
  the wrong one.
- The CSV asymmetry still holds: the CSV export carries no budgets either, so
  goals and limits remain SQLite-path-only and both surfaces must hide cleanly.

### D3.d — Budget cycle comes from the budget row; rendering follows the filter (2026-08-07)

**Decision, two parts.**

**1. The budget's own period is authoritative.** Do not assume monthly and do not
introduce a period setting in ERPNext. `Cashew Budget` stores `reoccurrence` and
`period_length` straight from the source row, and every window calculation
derives from `start_date` + those two fields.

Enum mapping to implement:

| `reoccurrence` | cycle |
|---|---|
| 0 | custom |
| 1 | daily |
| 2 | weekly |
| 3 | monthly |
| 4 | yearly |

`period_length` multiplies it — `3` + `2` is every two months.

**Assumption, explicitly flagged:** the 2026-07-04 export **cannot validate this
mapping**. Every transaction and both budgets carry the identical
`reoccurrence: 3, period_length: 1`, including one-off paid rows that are not
recurring at all — so `3/1` is Cashew's default stamp, not evidence. The mapping
matches Cashew's documented `BudgetReoccurence` enum order and `3` → monthly is
consistent with how the user describes both budgets, but it is unverified
against data.

**Guard:** an unrecognised `reoccurrence` value must **raise** at import, not
fall back to monthly. A wrong cycle silently misstates every budget figure on
the dashboard, and a silent default is exactly how that ships unnoticed.

**2. Rendering follows the selected period.**

- **Filter spans more than one budget cycle** → show **progress across cycles**.
  One mark per cycle against the limit line, so the trend is visible: a savings
  budget becomes a per-cycle series, a spending limit becomes per-cycle bars
  coloured over/under.
- **Filter spans one cycle or less** → show the **current cycle only**. Savings
  renders as the gauge; a spending limit renders as a single bar against
  its limit.

**This resolves the open question from the demo README** — a monthly budget
pro-rated across an all-time period is a number that exists nowhere in Cashew,
so it is never computed. The cycle is the unit; the filter selects how many of
them are shown.

**Consequences:**
- c009's gauge is no longer the only savings treatment. c009 owns both the
  single-cycle gauge and the multi-cycle series, switching on the filter.
- c013 does the same for spending limits.
- Cycle-bucketing runs off the budget's own anchor and cycle, **not** the
  dashboard's month buckets. A weekly budget over a 3-month filter yields ~13
  marks, not 3. c002's time-series must therefore expose enough granularity to
  aggregate per budget cycle — daily buckets are the safe floor.
- A partial trailing cycle (the filter ends mid-cycle) is shown, and marked
  partial, so a half-finished month does not read as a missed target.

**Side finding, outside f012's scope:** `objective_loan_fk` links 5 real
transactions to loan objectives. **f008 Transaction Reconciliation (Invoices &
Loans)** is currently specified with no knowledge of this field, yet it is a
direct loan signal in the source data — potentially better than the
category-based loan routing f006 built. Recorded as an f008 input; not acted on
here.

### D3.b — Expense breakdown is a treemap, not a sunburst (resolved 2026-08-07)

**Decision:** Ship a **treemap** for the expense category breakdown in v1.
Sunburst is deferred until subcategory data actually exists.

**Difference, since it drove the choice:** a sunburst is concentric rings — the
inner ring is the parent category, the outer ring its children, and its whole
point is showing hierarchy. A treemap is nested rectangles sized by value, and
it works well with a single flat level. **With one level and no children, a
sunburst degenerates into a plain donut** — the same chart the dashboard
already has, with extra machinery.

**Evidence this is the current situation:** f011's scan of the real Cashew
SQLite export found `sub_category_fk` unused across every row (0 rows populated),
so both the CSV and SQL paths produce a flat single-level category dimension
today.

**Rationale:** the treemap is the useful chart against the data that actually
exists — area encodes magnitude, it holds far more categories legibly than a
donut, and it does not pretend to a hierarchy that is not there.

**Forward path:** `<CsChart>` should keep the expense-breakdown component's
data contract hierarchical (nodes with an optional `children` array) even
though every node is a leaf today. Swapping treemap → sunburst then becomes a
chart-type change in one component, not a data reshape. If subcategories are
ever populated in Cashew, this is a cheap upgrade.

### D3.c — Invoice KPI card confirmed (resolved 2026-08-07)

The user confirmed the assumption: the **invoice** card shows **volume and
value of Sales and Purchase Invoices posted in the selected period**, not
outstanding AR/AP.

---

## Decision 4 — Chart colour: curated categorical palette, accent for primary (2026-08-07)

**Decision:** Multi-series and categorical charts use a **fixed, curated,
accessibility-checked categorical ramp** of roughly 8–10 hues, defined once in
the chart theme owned by `<CsChart>`. The Cashew accent
(`var(--cs-accent*)` / `cs.accent`) remains the primary and emphasis colour for
single-series charts, highlights, selection, and hover states.

**Options presented:** (a) curated palette + accent for primary, (b) derive the
whole ramp programmatically from `Cashew Settings.accent_color`, (c)
semantic-first fixed meanings only.

**Rationale:** deriving 8+ hues from one accent by rotation or lightness steps
reliably produces adjacent categories that are muddy or fail contrast — the
failure mode is exactly the "looks cheap" outcome this feature exists to fix.
A curated ramp is predictable and testable; keeping the accent as the emphasis
colour preserves brand coherence where it is actually noticed.

**This amends `.fb/system-arch/design-philosophy.md` point 6** ("Accent: only
`var(--cs-accent*)` / the `cs.accent` Tailwind color — never a hardcoded hex").
The amendment is narrow and must be written into the design philosophy doc:
*charts may use the named categorical ramp defined in the chart theme; that
ramp is the only sanctioned non-accent colour source, it lives in exactly one
file, and no chart or component may hardcode a hex outside it.*

**Semantic colours still apply on top of the ramp** — income, expense, and
transfer carry fixed meanings across every chart (they must not swap hue
between the trend chart and the sankey). TD locks the exact three.

**The ramp, locked 2026-08-07** (chosen and validated while building the demo;
these are the values to implement, not a suggestion):

| slot | light | dark |
|---|---|---|
| 1 indigo | `#4f46e5` | `#7c74f0` |
| 2 teal | `#0d9488` | `#2dd4bf` |
| 3 amber | `#d97706` | `#fbbf24` |
| 4 rose | `#e11d48` | `#fb7185` |
| 5 violet | `#7c3aed` | `#a78bfa` |
| 6 cyan | `#0891b2` | `#22d3ee` |
| 7 lime | `#65a30d` | `#a3e635` |
| 8 orange | `#ea580c` | `#fb923c` |
| 9 pink | `#be185d` | `#f472b6` |
| 10 slate | `#475569` | `#94a3b8` |

Semantic colours alongside it — income `#0f9d76` / `#34d399`, expense
`#e11d48` / `#fb7185`, transfer `#8b8d98` / `#7c7e8a`.

Slot 1 tracks the accent so a single-series chart and the ramp's first
category agree on the default Indigo theme. If the user picks a non-indigo
accent, slot 1 stays indigo and the accent still governs emphasis — the ramp
does not retint.

**Binding constraints for TD / Dev:**
- The ramp lives in one module consumed by the `<CsChart>` theme. No per-chart
  colour arrays.
- **zrender parses colours itself and does not understand CSS `color-mix()`.**
  Any translucent fill (area gradients, axis-pointer shadows) must be built as
  `rgba()` from the token hex, not handed to ECharts as a `color-mix()` string.
  Proven while building the demo; this will silently render black otherwise.
- Contrast-check the ramp against both the card surface and the sunburst /
  sankey label overlays before it is locked.
- The dashboard is currently light-surface only; if a dark mode is ever added,
  the ramp needs a dark variant — record that as a known future cost.

---

## Decision 5 — Pre-dev coherence pass (2026-08-07, later same day)

Everything above was written across one session and parts of it went stale as
later decisions superseded earlier ones. This section is the reconciliation
pass run before handing f012 to Quick dev. **Where this section disagrees with
anything above it, this section wins.**

A **fresh Cashew export** — `cashew-2026-08-07-00-20-33-593933.sql`, 652
transactions, replacing the 2026-07-04 file, which no longer exists on disk —
was scanned as part of this pass. It changed several facts. Those are C5.1
through C5.5; the stale-record fixes are C5.6 through C5.9.

### C5.1 — `budgets.wallet_fks` is the scope. The scalar `wallet_fk` is NOT.

**Corrects D3.a-ter's matching rule.** D3.a-ter recorded "Food outdoor" as
scoped to wallet Petty Cash. That came from the scalar `budgets.wallet_fk`.
The row actually carries `wallet_fks = NULL` and `wallet_fk = <Petty Cash>`.

The two readings produce different numbers — computed against the fresh export,
Food outdoor for 2026-07 is **36,146** under `wallet_fks` (null = all wallets)
and **33,890** under the scalar. Not a rounding difference; a wrong account
filter.

**Decision: `wallet_fks` is the account scope. NULL or `[]` means all wallets.
The scalar `wallet_fk` is a display/currency anchor and takes no part in
matching.** A limit named "Food outdoor" should count food spend wherever it
was paid from, which is also what the semantics say.

Corrected scope table:

| budget | amount | income | category scope | wallet scope |
|---|---|---|---|---|
| Savings | 50,000 | 1 | `Savings`, `Balance Correction` | wallet `Saving` |
| Food outdoor | 10,000 | 0 | `Entertainment` | **all wallets** |

### C5.2 — `category_fks_exclude` exists and the recorded matching rule omits it

The `budgets` table has **`category_fks_exclude`** alongside `category_fks`.
D3.a-ter's rule never mentions it. Live values are `NULL` (Savings) and `[]`
(Food outdoor), so it is inert today and nothing would have broken — which is
exactly why it would have been missed until a user set one.

**The complete matching rule, superseding D3.a-ter's:**

```
a transaction counts toward a budget when ALL hold:
  txn.paid is true
  bool(txn.income) == bool(budget.income)
  category_fks  is empty  OR  txn.category_fk in category_fks
  txn.category_fk NOT in category_fks_exclude
  wallet_fks    is empty  OR  txn.wallet_fk   in wallet_fks
```

### C5.3 — Category and wallet primary keys are NOT always UUIDs

`categories.category_pk` and `wallets.wallet_pk` are TEXT and Cashew's seeded
defaults use **small integer strings**: category `"0"` is Balance Correction,
`"5"` is Entertainment, wallet `"0"` is Investment. Both live budgets reference
them — Savings' `category_fks` is
`["32965a43-0fe7-4b23-8980-65488fde9348", "0"]`.

**Binding: never validate a Cashew FK as a UUID and never coerce it to one.**
Treat every `*_pk` / `*_fk` as an opaque string. A UUID-shaped regex or a
`uuid.UUID()` parse would silently drop the Balance Correction leg of the
user's savings budget.

### C5.4 — Budget dates are Unix epoch seconds, not ISO strings

`start_date` / `end_date` / `date_created` / `date_time_modified` on `budgets`
are integer epoch seconds. `1753988400` is `2025-08-01T00:00:00+05:00`.
Convert with the **site timezone**, the same discipline f011 c001 established
for transaction dates — a UTC conversion moves the anchor to the previous day
and shifts every derived cycle boundary by one.

The D3.a-ter `end_date` trap is re-confirmed on the fresh export: both budgets
are live, both carry an Aug 2025 `end_date`. `archived` is the inactive signal.

### C5.5 — `budget_transaction_filters` is an unrecognised dimension

Each budget carries `budget_transaction_filters` — `[6]` on Savings, `[5]` on
Food outdoor. The enum is undocumented in the export and the two live rows
disagree, so it cannot be inferred from data.

**Decision: ignore it, do not store it, do not let it affect matching.** The
computed actuals reproduce the user's expectation without it, and inventing a
meaning for an unknown enum is worse than omitting a filter that is currently
inert. **Recorded as a known unknown** — if a budget's ERP figure ever
disagrees with what Cashew shows on screen, this field is the first suspect.

**The `reoccurrence` enum is still unverified.** The fresh export did not help:
budgets are both `(3, 1)`, transactions are `(3, 1)` on 564 rows and
`(None, None)` on 88. `3/1` remains a default stamp, not evidence. D3.d's
raise-on-unrecognised-value guard stands and is now the only protection.

### C5.6 — Dark mode: the ramp has dark values, the SPA has none

Three places disagreed. `out_of_scope` says dark mode is out; Decision 4 says
"if a dark mode is ever added, the ramp needs a dark variant"; the locked ramp
table already has a full dark column and the approved demo ships a working
light/dark toggle.

Verified against the code: the SPA has **zero** `dark:` utilities and no
dark handling in `theme.js`. There is no dark mode.

**Decision: dark mode stays out of scope for f012.** The ramp's dark column is
kept as a recorded forward asset, not a deliverable. Decision 4's "if ever
added, the ramp needs a dark variant" is **obsolete** — the variant is already
chosen.

**Trap for dev: the demo's theme toggle must not be ported.** It exists because
the artifact renders in the viewer's theme. Copying it into the SPA ships a
half-dark dashboard inside an all-light application.

### C5.7 — Stale supersessions in `resolved_questions`

- **D3.a as recorded is wrong.** It still describes
  `Cashew Settings.savings_target_amount`, "per-month", and "pro-rated". All
  three were superseded — the field by D3.a-ter (goals come from Cashew's
  `budgets`), the pro-rating by D3.d (**never pro-rate a target**). The correct
  statement of D3.a is only this: *the gauge measures a fixed target amount,
  not a percentage rate.*
- **Decision 3's core list is stale in two rows.** Item 3 says "Expense
  sunburst" — superseded by D3.b (treemap). Item 6 says "Savings-rate gauge —
  `(income − expense) / income`" — superseded by D3.a and D3.d. The list is
  left as the historical record of what was chosen; the D3.x sections are
  authoritative.
- **All of D3.a-bis is superseded by D3.a-ter.** No `Cashew Goal` doctype, no
  `objectives` import, G1–G5 moot. The fresh export re-confirms the premise:
  `objectives` still holds only the two zero-amount loan trackers (and "General
  loan" is now archived).

### C5.8 — c002 granularity and balance history: RESOLVED

Both open questions on c002 are closed here rather than left for dev.

**Granularity — three blocks, each sized to its consumer, not one universal
bucket:**

| block | granularity | why |
|---|---|---|
| `daily_spend` | always daily | the calendar heatmap is daily by definition; one scalar per day is cheap even over all time (~550 values) |
| `series` (income/expense, per-category, balances) | daily when the period spans **≤ 92 days**, otherwise monthly | multi-series × daily × all-time is thousands of points nobody can read |
| `budget_cycles` | one bucket per budget cycle, **computed server-side per budget** | see below |

**This retires the "daily buckets are the floor" rule** from D3.d and the
matching `key_architecture` bullet. That rule existed so the client could
re-bucket daily data onto budget cycles. Having the server emit budget-anchored
buckets directly is simpler, is the only place that knows the anchor and the
enum, and removes the constraint from the general series entirely.

**Balance history: running GL sums, one grouped query plus a prefix sum**, not
period-end snapshots and not one query per bucket. Read the cumulative balance
per account as of the day before `period_start` in a single aggregate, then add
the per-bucket movement cumulatively in Python. Snapshots would need a store
that does not exist; per-bucket queries turn the dashboard's single round-trip
into N.

### C5.9 — c001 wrapper: RESOLVED

`vue-echarts`, imported in exactly one file, `<CsChart>`. Its resize and
lifecycle handling is the part worth not rewriting, and confining it to one
component keeps the swap to `echarts.init` a one-file change if it disappoints.

### C5.10 — c012 has no host: the importer is transaction-only

`importer/sqlite_reader.read_sqlite()` reads **transactions only** and returns
a flat list of row dicts matching the CSV parser's contract. There is no
second read pass, and `Cashew Import Run` is row-oriented — budgets are not
rows and must not become `Cashew Import Row` records.

**Decision: budgets import as a side-effect of the SQLite read, on their own
path.** A new `read_budgets(file_content) -> list[dict]` in `sqlite_reader.py`,
called by the import worker, upserting `Cashew Budget` on `budget_pk` outside
the row pipeline. It does not touch run counters, cannot fail a run, and a
revert does not remove budgets — they are reference data, not postings.

**Corollary: budgets are imported even on a date-windowed import.** The f011
c002 date window scopes transactions; a budget is not dated in that sense.

---

## Decision 6 — Budget scope must be fully mapped before import (2026-08-07)

**User decision, two parts, both taken 2026-08-07.**

A Cashew budget scopes itself to categories and wallets. Budget actuals on the
dashboard are computed from **GL Entry**, not from the Cashew file, so every
scope member has to resolve to an ERP account through `Cashew Category Mapping`
/ `Cashew Account Mapping` before a number can be produced. An unmapped scope
member is not a cosmetic gap — it is a **hole in the figure**, and it fails in
the dangerous direction: a spending limit missing one of its categories reads
*under* limit when it is blown.

**Part 1 — resolve completely before importing, not after.** A budget whose
scope is not fully mapped is **not imported**. The import surface presents every
unmapped category and wallet up front and requires them to be mapped before the
budget import proceeds. Rejected alternatives: importing and computing anyway
(silently wrong in the dangerous direction), and importing with a degraded
warning card (defers a decision the user is already in a position to make).

The block must never be a dead end. It is a **gate with the fix attached** — the
same screen that reports the problem resolves it.

**Part 2 — the mapping UI is inline in the SPA import surface.** Not a
deep-link. The user picks the ERP account for each unmapped Cashew category and
wallet without leaving the import, and a real `Cashew Category Mapping` /
`Cashew Account Mapping` row is written.

**This narrowly amends f010's "configuration UX stays on Desk" scope decision.**
The amendment is limited to *resolving mappings that block an in-progress
import*. Managing the mapping tables at large stays on Desk, and
`MappingsSection.vue` keeps its deep-links. The justification is that this is
not configuration work — it is the import telling the user what it needs in
order to finish, at the moment it needs it.

**Binding constraints:**
- Account pickers use the shared `<LinkField>` (SPA API discipline rule 2). A
  bare `<Autocomplete>` with `reference_doctype` is a silent no-op and will
  render an empty list.
- Writes go through a whitelisted `api.py` method calling
  `frappe.has_permission("Cashew Category Mapping", "create")` and the same for
  `Cashew Account Mapping` (rule 3). A user who cannot create mappings sees the
  blocked list read-only with a Desk link, not a broken form.
- Category mappings carry `category_type`, and f006 c001/c008 enforce
  account-class predicates on save. The inline form must surface those
  validation errors rather than swallowing them.
- Cashew PKs are opaque strings including integer-like ones (C5.3). The resolver
  keys on the PK and displays the name; it must not key on the display name.

**Reach beyond budgets, deliberate:** the same resolver answers the existing
row-level `MAPPING_NOT_FOUND` / `CASHEW_ACCOUNT_NOT_MAPPED` queue-time errors,
which today can only be fixed on Desk. It is scoped as a general
unmapped-Cashew-entity resolver with budgets as its first consumer — see c014.

---

## Decision 7 — No opening entry. The negative curve is real, and the missing decade of history is an optional backfill (2026-08-07)

**Two conclusions, reached independently and then reconciled.** Asked where the
real opening figures should come from, the user said to take them from the SQL
file. Checking whether that was possible showed the premise was wrong — and
`system-arch/import-integrity-2026-08-07.md` finding 1 had already been
**withdrawn** for the same reason, by a separate pass, before this one ran.

**Conclusion 1 — there is no opening balance to post, for any account.**
Confirmed twice from the same file by two independent computations that agree to
the cent: Petty Cash stood at **0.28** on 2026-03-04, the day before the ERP's
import window opens, and ERPNext already holds exactly that. Saving stood at
214,695.00 and is exact in ERPNext. Every other imported wallet opened at zero.

The deep negative is **what the source data says**, not an artefact. Cashew's
*own* running balance for Petty Cash reaches **−117,357.72 on 2026-01-01**,
months before ERPNext knew the account existed. A wallet that goes deeply
negative in Cashew goes deeply negative in ERPNext, correctly.

**`importer/opening.py` stays as a general capability. Nothing is posted for
this company. Do not reinstate the opening-balance prerequisite.**

Two real gaps remain from the integrity pass, neither an opening-balance issue
and neither blocking any component: Elevate Pay reads −1,238.85 PKR on live
until the f013 repost script runs (one entry, `ACC-JV-2026-00275`), and Petty
Cash is 1,324.00 PKR below Cashew for reasons not yet traced, with NSave 18.00
USD above it from a manual JE (`ACC-JV-2026-00625`).

**Conclusion 2 — separately, ten and a half months of history was never
imported. That is a real gap, but it is a missed opportunity, not a defect.**

**What the live ledger actually holds** (REST read against `erp.nstack.xyz`,
2026-08-07, reconciled against `cashew-2026-08-07-00-20-33-593933.sql`):

| month | Cashew paid txns | ERP submitted JEs | |
|---|---|---|---|
| 2025-02 … 2025-11 | 218 | **0** | entirely absent |
| 2025-12 | 48 | 1 | almost entirely absent |
| 2026-01 | 16 | 9 | partial |
| 2026-02 | 47 | 13 | partial |
| 2026-03 … 2026-06 | 216 | 243 | covered |
| 2026-07 | 95 | 92 | near-covered |
| 2026-08 | 11 | **0** | absent |
| **total** | **651** | **358** | |

Earliest GL Entry is **2025-12-01**. Cashew's own history starts **2025-02-05**.
The completed import runs cover May, June and July 2026 plus two early undated
CSV runs — roughly **ten and a half months of history was never imported.**

The import runs were **deliberately windowed from 2026-03-05 onward** — this is
not an importer failure, it is simply where the user started importing. But for
a feature whose entire purpose is historical charts, thirteen months of
unimported history is the single cheapest improvement available to it.

**BACKFILL DECLINED BY THE USER (2026-08-07).** Offered and turned down: imports
run regularly on the live site from the point the app was installed, and the
pre-installation history is not wanted. **Do not re-raise this.** The rest of
this section is kept as the record of what was offered and why.

**Consequence to design for:** the dashboard has roughly 5–6 months of history
at build time, growing forward. The calendar heatmap renders part of one year,
not a multi-year grid; most period selections land on the *daily* side of
C5.8's 92-day switch; and the single-cycle gauge is the common case for c009,
not the edge case.

**The only thing genuinely missing from the live site is budgets** — never
imported because the importer has never read them. That is c012, a build task,
not a data task.

~~Optional backfill (recommended, needs the user's go-ahead)~~ — re-run the
date-windowed SQLite import against
`cashew-2026-08-07-00-20-33-593933.sql`. f011 c002 already does this; **no new
code is required.** Suggested windows, largest gap first:
`2025-02-05 → 2025-11-30` (218 transactions), then `2025-12-01 → 2026-02-28`,
then `2026-08-01 → 2026-08-06`.

Re-importing an overlapping window is safe: `apply_idempotency_guard` skips rows
whose hash already resolves to a **submitted** document. It filters on
`docstatus = 1`, so a row whose JE was cancelled *will* repost — the desired
behaviour here.

Expect the backfill to surface unmapped categories and wallets from ten months
of previously unseen data. That is exactly c014's job, which is why c014 is
worth building **before** the backfill rather than after.

**Consequences:**
- The opening-balance prerequisite is **rescinded and must not be reinstated**.
  c005 / c008 / c010 are **ungated** — build them in wave 2 with everything else.
- The backfill is a large win for f012 on its own terms: roughly 5 months of
  usable chart history becomes 18. It is **not** a prerequisite; every component
  builds and renders correctly without it.
- It is an **operational action on live data**, not build work. Explicit
  go-ahead per window, and a backup before the first run.

**Flagged, not decided:** Investment sits at −447,850 permanently in Cashew —
money recorded leaving for investments with no asset recognised. That is a
modelling question about how investment transfers should post, not a data gap,
and it will render as a large negative band on c010 either way. The account is
not currently mapped into ERPNext, so the backfill would introduce it; worth a
decision before running the 2025 window.

---

## Data-quality caveat — raised, not a decision (2026-08-07)

The 2026-08-07 REST verification pass
(`.fb/system-arch/import-integrity-2026-08-07.md`) found real problems in the
data this dashboard renders:

- **No opening balances were ever imported.** Cashew history starts 2026-03-05
  with nothing before it, so the ledger sits on a floor of zero — Petty Cash
  runs to −132,313.22 at its worst. A net-worth chart, a balance-history area,
  and an account stacked area will all plot deeply negative cash.
- `ACC-JV-2026-00042` is cancelled but still claimed as posted by run 000001,
  overstating Petty Cash by 13,750.
- Same-currency foreign transfers post at rate 1.0 (`posting.py:132-140`),
  so at least one USD 4.50 transfer is booked as PKR 4.50.
- All 20 USD Transfer rows carry `exchange_rate` / `base_amount` = 0
  (`mapping.py:202` skips Transfers), so anything reading `base_amount`
  undercounts transfers — the sankey is the chart most exposed to this.

**Position:** f012 does not fix these — they are separate defects with their own
owners. But better charts make wrong numbers *more* visible, not less, and the
balance-history and sankey charts are the two that will surface them loudest.
Worth sequencing the opening-balance entry ahead of, or alongside, c005 and
c008 rather than after.

**Status update (2026-08-07, coherence pass): f013 Import Integrity is DONE and
closes most of this.** The cancelled-JE drift, the same-currency FX bug, and
the missing Transfer `base_amount` are fixed in code (f013 c001, c002). The
sankey's exposure to zero-valued transfers is gone.

**One item is NOT closed.** Every cash account still floors at zero and Petty
Cash still dips to −132,313.22.

**SUPERSEDED BY DECISION 7 (same day), and by the withdrawal of finding 1 in
`system-arch/import-integrity-2026-08-07.md`.** This caveat read the symptom as
a missing opening entry. It is not one. Petty Cash stood at 0.28 the day before
the import window and ERPNext holds exactly that; Cashew's own running balance
reaches −117,357.72 on 2026-01-01. **The negative curve is what the source data
says.** Nothing is posted, no component is gated, and the opening-balance
prerequisite must not be reinstated.

