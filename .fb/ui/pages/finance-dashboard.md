# Page: Finance Dashboard

> **Stack:** Vue 3 SPA (frappe-ui)
> **Component ID:** `c007` (`finance-dashboard-page`)
> **Route:** `/` (SPA landing page)
> **Shell:** see [`../shell.md`](../shell.md) — sidebar + app switcher always present around this page
> **Arch refs:** D9 (finance dashboard, not run aggregates), D5 (API discipline), D6 (session-only state), D8 (realtime)

---

## 1. Page brief (for Claude Design)

A **finance overview dashboard** that loads when an operator or manager opens `/cashew`. It is the default landing page. The user sees this most of the time because Cashew imports run roughly once per month — between imports, this is the screen they keep open.

**What it answers at a glance:**
- How much income vs expense for the selected period?
- What are the current cash, receivable, and payable balances?
- Which categories drove the period's income and expense?
- What was the last import, and is anything in flight?

**Tone:** professional finance dashboard. Information-dense but uncluttered. Easy to scan in 5 seconds.

**Inspirations** (for designer reference): Frappe CRM's Insights dashboard layout density; QuickBooks Dashboard tile style for the balance summary; Stripe Dashboard's restrained chart palette.

---

## 2. Audience & flow

- **Primary:** finance operators + accounting managers using ERPNext for their books.
- **When they're here:** every morning / week, to check totals; right after running a monthly import, to verify it landed in the GL.
- **What they do here:**
  1. Land on the dashboard (default route).
  2. Glance at totals + tiles.
  3. Maybe change the period to last month / FY-to-date.
  4. Either close the tab OR click into a recent import to inspect it.

---

## 3. Layout

Single-page, vertical-stacked content area (sidebar handled by shell). Sections from top to bottom:

```
┌───────────────────────────────────────────────────────────┐
│ A. Page Header                                            │
│   Title + Period Selector (+ Company Selector if multi-co)│
├───────────────────────────────────────────────────────────┤
│ B. Balance Tile Grid                                      │
│   [Cash & Bank] [Receivable] [Payable] [Net This Period] │
├──────────────────────────────┬────────────────────────────┤
│ C. Income vs Expense Chart   │ D. Category Breakdown      │
│   (donut or stacked bar)     │   Top income categories    │
│                              │   Top expense categories   │
├──────────────────────────────┴────────────────────────────┤
│ E. Recent Imports Strip                                   │
│   [run] [run] [run] [run] [run]   "View all imports →"   │
└───────────────────────────────────────────────────────────┘
```

Responsive collapse:
- Desktop (≥1024px): layout as drawn (C + D side by side).
- Tablet (640–1023px): C and D stack vertically; tile grid stays 4-up.
- Mobile (<640px): everything stacks; tile grid becomes 2×2 (or 1-column for narrow phones).

---

## 4. Components

Below: every component on this page, with all fields/actions Claude Design must include. Field labels and types come from real DocType definitions (cashew_integration) and from the strawman shape of the `dashboard_summary` API endpoint (per D9).

### A. PageHeader

**Purpose:** Page title + period filter + (conditionally) company filter. Anchors the page; rendered once at the top.

**Layout:** Single row. Left: page title. Right: period selector (and company selector if visible).

**Display fields:**
| Element | Value | Type | Source |
|---|---|---|---|
| Page title | `Finance Dashboard` | static | hardcoded |
| Subtitle / breadcrumb | (none) | — | — |

**Embedded controls:**
- `PeriodSelector` (see below)
- `CompanySelector` (conditional — only shown if >1 company; see below)

**States:** static.

---

### A.1 PeriodSelector

**Purpose:** Pick the reporting period. Drives every data fetch on this page.

**Display:** Pill-shaped dropdown button. Label shows current selection (e.g. `This Month: May 2026`). Chevron-down.

**Dropdown options:**
| Preset | Resolves to |
|---|---|
| This Month | First day of current month → today |
| Last Month | First day → last day of previous month |
| Last 30 Days | Today − 30 days → today |
| Last 90 Days | Today − 90 days → today |
| This Fiscal Year | Fiscal year start (from Frappe `Fiscal Year` for current date) → today |
| Custom Range… | Opens a date-range picker (two calendars) |

**Default selection on first load:** `This Month`.

**Behaviour:**
- Selecting a preset closes the dropdown and re-fetches `dashboard_summary`.
- Selecting `Custom Range` keeps dropdown open; date picker appears; pressing **Apply** closes and re-fetches.

**State persistence:** Session only (D6). On full page reload, defaults back to `This Month`.

**Data emitted:** `{ start: "YYYY-MM-DD", end: "YYYY-MM-DD", preset: "this-month" | ... | "custom" }`.

**States:**
- Default
- Open (dropdown visible)
- Custom-range editing
- Loading (after change, until data returns — show a small spinner inside the pill)

---

### A.2 CompanySelector *(conditional)*

**Purpose:** Switch which company the dashboard reflects. Only rendered when the user has access to >1 company; otherwise hidden and the page just uses `window.boot.default_company`.

**Display:** Frappe-ui `<Autocomplete>` chip styled like the PeriodSelector. Shows current company name.

**Field:**
| Field | Type | Source |
|---|---|---|
| Selected company | Link to DocType `Company` | `frappe.desk.search.search_link?doctype=Company` (D5 rule 2) |

**Default:** `window.boot.default_company`.

**Behaviour:** Picking a different company re-fetches `dashboard_summary`.

**State persistence:** Session only.

---

### B. BalanceTileGrid

**Purpose:** Top-row summary tiles — the "headline numbers" of the dashboard.

**Layout:** Horizontal 4-column grid. Each tile is a card.

**Tiles (in order):**

| # | Label | Value | Currency | Optional delta | Icon |
|---|---|---|---|---|---|
| 1 | `Cash & Bank` | sum of balances across asset-type Bank + Cash accounts as of `period.end` | from `boot.default_currency` or `dashboard_summary.currency` | vs `period.start` balance (∆ absolute + %) | `wallet` |
| 2 | `Receivable` | total receivable balance as of `period.end` (sum across Accounts where `account_type = "Receivable"`) | same | vs prior period | `arrow-down-circle` |
| 3 | `Payable` | total payable balance as of `period.end` (sum across `account_type = "Payable"`) | same | vs prior period | `arrow-up-circle` |
| 4 | `Net This Period` | `income_total − expense_total` for `[period.start, period.end]` | same | (no delta — it's already a delta) | `trending-up` (or `trending-down` if negative) |

**Display per tile:**
- Top: icon + label (small, muted)
- Middle: big formatted amount (currency symbol + locale-formatted number, e.g. `₹ 1,24,500.00` or `$ 124,500.00`)
- Bottom: delta chip (e.g. `↑ 12.4% vs last month`) — green when favorable, red when unfavorable. Hidden if no prior-period data.

**Data fields (from `dashboard_summary`):**
```
balance_tiles: {
  cash_bank: { amount: number, prior_amount: number | null },
  receivable: { amount: number, prior_amount: number | null },
  payable: { amount: number, prior_amount: number | null },
  net_for_period: { amount: number }       // no prior delta
}
currency: string                            // ISO code, e.g. "INR"
```

**States:**
- Loading — skeleton bars in place of each tile (label visible, amount shimmering)
- Loaded — values + deltas as above
- Empty — amount renders as `—` (em-dash) and label "No data for this period"
- Error — tile shows `Could not load` in red text; refresh icon button retries

**Interactions:** None in v1. (Future: click tile → drill to ledger report for that account group. Not v1.)

---

### C. IncomeExpenseChart

**Purpose:** One visual that says "here's how the period went". Income vs Expense for the selected period.

**Display:** Card with header + chart body.

**Card header:**
- Title: `Income vs Expense`
- Period subtitle: `{period.start} – {period.end}` (formatted as "May 1 – May 24, 2026")
- Right-side: total formatted "Income: ₹ X | Expense: ₹ Y | Net: ₹ Z" in small text

**Chart body:**
- **Visual type:** donut chart (preferred) with two slices, OR side-by-side bar chart. Designer to pick whichever reads cleaner at this size.
- **Slice 1: Income** — green/teal. Tooltip on hover: "Income: ₹ X (N% of total)"
- **Slice 2: Expense** — orange/red. Tooltip on hover: "Expense: ₹ Y (M% of total)"
- Center label (donut variant): big "Net" amount, with arrow up/down.

**Data fields:**
```
income_total: number
expense_total: number
currency: string
period: { start: "YYYY-MM-DD", end: "YYYY-MM-DD" }
```

**States:**
- Loading — skeleton circle / shimmer
- Loaded — chart with values
- Empty — placeholder graphic + text "No transactions in this period"
- Error — "Could not load chart" + retry icon

**Interactions:** Hover for tooltips. v1 has no drill-in click.

**Library hint:** frappe-ui chart wrapper if it covers donut + bar; else chart.js. Locked by TD at component spec.

---

### D. CategoryBreakdownCard

**Purpose:** Show which categories drove the income and the expense, so the user can scan top contributors.

**Display:** Card with two list sections (top income / top expense). Can render as side-by-side columns OR stacked sections inside one card — designer picks based on width.

**Card header:**
- Title: `Top Categories`
- Subtitle: same period as above
- Small toggle / segmented control on the right: `Income | Expense` (if showing one at a time) — OR show both panels at once if there's room.

**For each category list (Income side AND Expense side):**

| Element | Value | Type | Source |
|---|---|---|---|
| Section header | `Income` or `Expense` | static | — |
| Row 1..N | One row per category | repeated | `dashboard_summary.income_by_category` / `expense_by_category` |
| Row icon | Category icon (or first-letter chip) | optional | — |
| Row label | Category name | string | `category` field from row |
| Row amount | Formatted currency | currency | `amount` field |
| Row bar | Horizontal bar — fill width proportional to (this amount / max amount in this list) | visual | derived |
| Empty state | "No income in this period." or "No expenses in this period." | static fallback | — |

**Row count:** Top 5 per side (configurable from API; v1 show 5). Optional "View all categories →" link at the bottom of the list (deferred — out of v1, omit if no target page).

**Data fields:**
```
income_by_category: [
  { category: string, amount: number },   // ordered descending by amount
  ...                                      // up to 5
]
expense_by_category: [
  { category: string, amount: number },
  ...
]
currency: string
```

> `category` values come from `Cashew Category Mapping.cashew_category` (the Cashew-side category name; e.g. "Food", "Salary", "Rent"). For rows that posted to GL accounts directly without a category mapping, the API groups under `(Uncategorized)`.

**States:** Loading skeleton list / Loaded / Empty (per side) / Error.

**Interactions:** v1 — none. (Future: click row → filtered transaction list. Not v1.)

---

### E. RecentImportsStrip

**Purpose:** Show the last few imports so the user can quickly see if anything's in flight or recently posted, and click through to inspect. This is the dashboard's drill-in to the import workflow.

**Display:** Horizontal scrolling row of compact "import cards". Designed for 4–5 visible on desktop, 2–3 on tablet, 1.5 on mobile (with horizontal scroll indicator).

**Strip header:**
- Title: `Recent Imports`
- Right: text link `View all imports →` (routes to `/runs`)

**Per import card:**

| Element | Value | Type | Source |
|---|---|---|---|
| Run name | e.g. `CASHEW-IMPORT-2026-000017` | string | `Cashew Import Run.name` |
| Status pill | colored pill — see status table below | enum | `Cashew Import Run.status` |
| Period | `Period: Apr 1 – Apr 30, 2026` | date range | `period_start`, `period_end` |
| Row counts | `124 valid · 2 failed` (compact, only shows non-zero) | int counts | `rows_valid`, `rows_failed` (and `rows_total` if helpful) |
| Posted indicator | small "✓ N posted" if `rows_posted > 0` | int | `rows_posted` |
| Last updated | `Updated 2h ago` (relative time) | datetime | `modified` (Frappe standard field) |

**Status pill mapping (uses shared `StatusPill` component):**

| `Cashew Import Run.status` | Pill label | Pill color |
|---|---|---|
| `Draft` | Draft | grey |
| `Parsed` | Parsed | blue (light) |
| `Validated` | Validated | blue |
| `Queued` | Queued | indigo |
| `Processing` | Processing | indigo + animated pulse |
| `Completed` | Completed | green |
| `Failed` | Failed | red |
| `Cancelled` | Cancelled | grey (darker) |
| `Reverting` | Reverting | amber + pulse |
| `Reverted` | Reverted | amber |
| `Revert-Failed` | Revert Failed | red |

**Data source:** `dashboard_summary.recent_runs` (top 5, ordered `modified desc`). Each entry has the fields above; no separate fetch.

**Behaviour:** Clicking anywhere on a card → `router.push('/runs/:run_name')`. Cursor: pointer.

**States:**
- Loading — skeleton cards (5 placeholder cards shimmering)
- Loaded — cards as above
- Empty — placeholder text: "No imports yet." + button `+ New Import` → `/runs/new`
- Error — "Could not load recent imports" + retry icon

---

### F. DashboardEmptyState *(rendered only when applicable)*

**Purpose:** When the selected period has no GL data **AND** no recent runs (i.e. fresh install / brand-new period), replace the entire content area below the header with a single centered empty state instead of empty tiles + empty charts.

**Display:** Centered illustration (line art, no specific brand), title, body, primary CTA.

**Content:**
- Illustration: simple line-drawing of a bar chart with a "+" overlay
- Title: `Nothing to show for this period.`
- Body: `Once Cashew imports are posted to the General Ledger, totals and charts will appear here. Run your first import to get started.`
- Primary button: `+ Start an Import` → `/runs/new`
- Secondary link: `Change period` → focuses the PeriodSelector

**When rendered:** When `dashboard_summary` returns `income_total == 0 && expense_total == 0 && balance_tiles.*.amount == 0 && recent_runs.length == 0`.

**When NOT rendered:** If any of the above are non-zero, render the normal layout.

---

## 5. Data sources

### Single API call on mount + on filter change

`GET /api/method/cashew_integration.api.dashboard_summary`

**Request params:**
| Param | Type | Required | Source |
|---|---|---|---|
| `period_start` | Date `YYYY-MM-DD` | yes | `PeriodSelector.modelValue.start` |
| `period_end` | Date `YYYY-MM-DD` | yes | `PeriodSelector.modelValue.end` |
| `company` | string (Company name) | yes | `CompanySelector` or `boot.default_company` |

**Response (strawman; TD finalizes in c007 spec — see D9):**
```json
{
  "period": { "start": "2026-05-01", "end": "2026-05-24" },
  "currency": "INR",
  "income_total": 152400.00,
  "expense_total": 88350.50,
  "income_by_category": [
    { "category": "Salary", "amount": 100000.00 },
    { "category": "Consulting", "amount": 35000.00 },
    { "category": "Interest", "amount": 12400.00 },
    { "category": "Refunds", "amount": 3500.00 },
    { "category": "Other", "amount": 1500.00 }
  ],
  "expense_by_category": [
    { "category": "Rent", "amount": 35000.00 },
    { "category": "Food", "amount": 18250.50 },
    { "category": "Travel", "amount": 12100.00 },
    { "category": "Utilities", "amount": 9500.00 },
    { "category": "Subscriptions", "amount": 6800.00 }
  ],
  "balance_tiles": {
    "cash_bank":   { "amount": 425000.00, "prior_amount": 380000.00 },
    "receivable":  { "amount":  85000.00, "prior_amount":  95000.00 },
    "payable":     { "amount":  42000.00, "prior_amount":  38000.00 },
    "net_for_period": { "amount": 64049.50 }
  },
  "recent_runs": [
    {
      "name": "CASHEW-IMPORT-2026-000017",
      "status": "Completed",
      "period_start": "2026-04-01",
      "period_end": "2026-04-30",
      "rows_total": 126,
      "rows_valid": 124,
      "rows_failed": 2,
      "rows_posted": 124,
      "rows_skipped": 0,
      "modified": "2026-05-02T09:14:22"
    }
    // up to 5
  ]
}
```

**Realtime (per D8):** On mount, subscribe to `Cashew Import Run` `doc_update` (list-level). Any update fires a debounced re-fetch of `dashboard_summary` (debounce ~2s to avoid stampedes during posting). Connection status reflected by shell's `RealtimeStatusIndicator`.

---

## 6. Page-level states

| State | What it looks like |
|---|---|
| Initial load | All sections in skeleton/shimmer mode. PeriodSelector defaults to "This Month" but disabled until first response. |
| Loaded | All components render real data. |
| Empty | `DashboardEmptyState` replaces sections B–E (header stays). |
| Filter change loading | Components dim slightly, individual loading shimmers run on tiles + chart + lists. Header stays interactive. |
| Error (whole-page) | If `dashboard_summary` fails: shell-level toast (D5.c) + a centered card replacing B–E with "Could not load dashboard" + retry button. |
| Realtime updating | Brief shimmer pulse on whichever component changed (designer choice — could be a subtle border-highlight 500ms). |

---

## 7. Responsive notes

| Breakpoint | Layout shifts |
|---|---|
| ≥1280px | Tile grid 4 cols. C + D side-by-side, 2/3 + 1/3 split. Strip cards 5 visible. |
| 1024–1279px | Tile grid 4 cols. C + D side-by-side, 1/2 + 1/2. Strip 4 visible. |
| 768–1023px | Tile grid 4 cols (smaller). C + D stack. Strip 3 visible. |
| 640–767px | Tile grid 2 cols. C + D stack. Strip 2 visible. |
| <640px | Tile grid 2 cols (or 1 if very narrow). C + D stack. Strip 1.5 visible (horizontal scroll). PageHeader: title above, period selector below. |

Sidebar (shell) collapses to hamburger at <640px.

---

## 8. Accessibility

- All charts have an alt-text summary read by screen readers (e.g. "Income ₹152,400, Expense ₹88,350, Net ₹64,049 for May 2026").
- PeriodSelector dropdown is keyboard-navigable; Custom Range date pickers are reachable via Tab.
- All tiles and recent-import cards are real links (`<a>` or `<router-link>`), not click-handlers on divs.
- Color is never the only signal — every delta arrow has a sign character + label.

---

## 9. Components used from shared library

| Shared component | Where used here | See |
|---|---|---|
| `StatusPill` | RecentImportsStrip card status | `../shared-components.md` |
| `AmountDisplay` | All money values (tiles, chart labels, category amounts, etc.) | `../shared-components.md` |
| `EmptyState` (generic) | `DashboardEmptyState` is a specialization | `../shared-components.md` |
| `SkeletonBlock` | Loading shimmers across components | `../shared-components.md` |

---

## 10. DocType field requests *(open flag from arch UI-phase)*

None for this page. Dashboard reads from GL Entry + Account directly; no schema additions required.

---

## 11. Out of scope (v1) — explicit

- Click-to-drill into tile → ledger report (defer)
- Click-to-drill into chart slice → transaction list (defer)
- Multi-currency presentation (use company currency only)
- Customizable tile selection / dashboard widgets (no preferences)
- Export to PDF / CSV (defer — operators can export from the imports themselves)
- Saved presets for periods (D6 — session-only state)

---

## 12. Designer notes (Claude Design)

- Lean into clarity over decoration. Big numbers should be the biggest thing on the page.
- Tile spacing should be generous — these are headline numbers; don't crowd them.
- Use a restrained palette: a primary accent (Cashew brand, TBD), green for positive/income, red-amber for negative/expense, neutral greys for chrome.
- Status pills already have semantic colors — don't override.
- Recent imports cards should look "clickable" — subtle hover lift / border accent.
- The whole page should feel like a finance product, not a generic SaaS dashboard.
