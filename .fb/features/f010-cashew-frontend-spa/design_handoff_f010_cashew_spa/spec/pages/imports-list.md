# Page: Imports List

> **Stack:** Vue 3 SPA (frappe-ui)
> **Component ID:** `c005` (`imports-list-page`)
> **Route:** `/runs`
> **Shell:** see [`../shell.md`](../shell.md) — sidebar + app switcher always present
> **Arch refs:** D5 (API discipline — reads via `frappe.client.get_list`), D6 (session-only state), D8 (realtime)

---

## 1. Page brief (for Claude Design)

A **searchable, filterable table of every Cashew Import Run**. Reached from the sidebar "Imports" link, or via the dashboard's "View all imports" link, or after creating/saving a run. The operator's home for picking up where they left off — find a half-validated run, jump in. Also the entry point for starting a brand-new import via a prominent "+ New Import" button.

**What it answers at a glance:**
- What imports exist?
- Which ones are in flight (Processing / Queued)?
- Which ones failed and need attention?
- Which one was the most recent successful post?

**Tone:** dense but readable list view, classic data table. Frappe List view inspiration, but cleaner — no Frappe Desk chrome, no awkward filter modal.

---

## 2. Audience & flow

- **Primary:** finance operators running imports.
- **When they're here:** at the start of a new import (click "+ New Import"); after dashboard glance ("let me check that recent run"); after a Socket.IO update tells them something changed (the row visibly updates in place).
- **What they do here:**
  1. Optional: filter by status / period / company.
  2. Click a row → opens that run in the Workspace page.
  3. Or click "+ New Import" → opens Workspace in Upload state.

---

## 3. Layout

Single column. Header row across the top, then a full-width table below, with pagination at the bottom.

```
┌───────────────────────────────────────────────────────────┐
│ A. Page Header                                            │
│   Title  +  search input  +  [+ New Import] button        │
├───────────────────────────────────────────────────────────┤
│ B. Filter Bar                                             │
│   [Status ▾] [Period ▾] [Company ▾]   "Clear filters ×"   │
├───────────────────────────────────────────────────────────┤
│ C. Runs Table                                             │
│   ┌─────┬──────┬─────────┬──────┬──────┬─────┬─────┐      │
│   │Name │Status│Period   │Total │Valid │Fail │Upd. │      │
│   ├─────┼──────┼─────────┼──────┼──────┼─────┼─────┤      │
│   │...                                              │      │
│   └──────────────────────────────────────────────────┘     │
├───────────────────────────────────────────────────────────┤
│ D. Pagination                                             │
│   "Showing 1–25 of 124"   [<] [1][2][3][...] [>]          │
└───────────────────────────────────────────────────────────┘
```

Responsive collapse:
- Desktop / tablet: full table.
- Mobile (<640px): table collapses to a **card list** — one card per run, key fields stacked (see Component C variant).

---

## 4. Components

### A. PageHeader

**Purpose:** Page title + global search + primary CTA.

**Layout:** Single row. Left: title. Middle: search input (flex-grow). Right: "+ New Import" primary button.

| Element | Value | Type | Notes |
|---|---|---|---|
| Page title | `Imports` | static | h1 |
| Subtitle | `{N} runs total` | dynamic count | small muted text under title (optional) |
| Search input | text input | string | placeholder: "Search by run name…" |
| Primary button | `+ New Import` | button (action) | routes to `/runs/new` |

**Search behaviour:**
- Filters the run list client-side OR server-side (TD picks; v1 strawman = server-side via `frappe.client.get_list` filter on `name like %term%`).
- 250ms debounce.
- Empty clears the filter.

**Button behaviour:** `router.push('/runs/new')`.

**States:** static; button has hover/focus/active.

---

### B. FilterBar

**Purpose:** Narrow the table by status, period, and company. Stays at top of table.

**Layout:** Horizontal row of dropdown filter chips, with a "Clear filters" link on the right when any filter is active.

#### B.1 StatusFilter

**Display:** Multi-select dropdown chip. Label: `Status` (or `Status: 2 selected` when active).

**Options (every value in `Cashew Import Run.status`):**
| Value | Display |
|---|---|
| `Draft` | Draft |
| `Parsed` | Parsed |
| `Validated` | Validated |
| `Queued` | Queued |
| `Processing` | Processing |
| `Completed` | Completed |
| `Failed` | Failed |
| `Cancelled` | Cancelled |
| `Reverting` | Reverting |
| `Reverted` | Reverted |
| `Revert-Failed` | Revert Failed |

Plus a "Select all" / "Clear" at top of the menu.

**Behaviour:** Selecting/unselecting re-fetches the list with `filters: [["status", "in", [...]]]`.

#### B.2 PeriodFilter

**Display:** Single-select dropdown chip. Label: `Period` (or `Period: This Month`).

**Options:** Same presets as the dashboard `PeriodSelector` (This Month / Last Month / Last 30d / Last 90d / This Fiscal Year / Custom Range / Any). Default: `Any` (no filter).

**Filter field:** Filters by `period_start` overlap with the selected range (rows whose `period_start ≤ range.end AND period_end ≥ range.start` are kept).

**Behaviour:** Same as dashboard PeriodSelector — re-fetches on change.

#### B.3 CompanyFilter *(conditional)*

**Display:** Frappe-ui `<Autocomplete>` chip. Label: `Company` (or company name when set).

**Field:** Link to `Company`. Uses `search_link` per D5 rule 2 (`reference_doctype="Company"`).

**Hidden when:** user has access to only one company.

**Default:** Empty (no filter) — operator can scope explicitly.

#### B.4 Clear filters link

**Display:** Plain text link `Clear filters ×`, right-aligned in the filter bar.

**Behaviour:** Visible only when any filter is non-default. Click resets all filters.

---

### C. RunsTable

**Purpose:** The main content. Tabular list of every Cashew Import Run matching the current filters.

**Columns (desktop, in order):**

| # | Header | Data | Source field | Format |
|---|---|---|---|---|
| 1 | `Run` | run identifier — clickable | `name` | monospace, e.g. `CASHEW-IMPORT-2026-000017` |
| 2 | `Status` | colored pill | `status` | uses shared `StatusPill` |
| 3 | `Company` | company name | `company` | text (truncate if long) |
| 4 | `Period` | date range | `period_start` + `period_end` | `Apr 1 – Apr 30, 2026` (or `—` if either is null) |
| 5 | `Total` | total rows | `rows_total` | right-aligned int |
| 6 | `Valid` | valid rows | `rows_valid` | right-aligned int (green if all valid) |
| 7 | `Failed` | failed rows | `rows_failed` | right-aligned int (red if > 0) |
| 8 | `Posted` | posted rows | `rows_posted` | right-aligned int |
| 9 | `Updated` | last modified | `modified` (Frappe std field) | relative ("2h ago") with absolute timestamp on hover |
| 10 | `…` | row-action menu | — | kebab icon → menu (see below) |

**Sort:** click column header. v1 sortable columns: `Status`, `Period` (by `period_start`), `Updated`. Default sort: `modified desc`.

**Row click:** anywhere on the row (except the kebab menu) routes to `/runs/:name`.

**Row hover:** subtle background + cursor:pointer.

**Row-action menu (kebab):**
| Action | Target | Condition |
|---|---|---|
| Open in workspace | `/runs/:name` | always (also the row click) |
| Open Desk form (legacy) | `/app/cashew-import-run/:name` | always — escape hatch |
| Download diagnostics CSV | `diagnostics_file` URL | only when `status in ("Completed", "Failed", "Revert-Failed")` and `diagnostics_file` is set |
| Revert | calls `revert_run(name)` w/ confirm dialog | only when `status == "Completed"` |
| Cancel | calls `cancel_run(name)` w/ confirm dialog | only when `status in ("Queued", "Processing")` |

**Mobile variant (card list, <640px):**

Each row becomes a card:
```
┌────────────────────────────────────┐
│ CASHEW-IMPORT-2026-000017          │
│ [Completed]   Updated 2h ago       │
│ Apr 1 – Apr 30, 2026               │
│ 124 valid / 2 failed / 124 posted  │
│ Acme Pvt Ltd                       │
│                              [⋯]   │
└────────────────────────────────────┘
```

**Realtime (per D8):** Subscribed to `Cashew Import Run` `doc_update` events. Any matching run updates in place (status pill, counters, "Updated" timestamp). New runs (created by another user) appear at the top with a brief highlight pulse.

**States:**
- Loading — skeleton rows (or skeleton cards on mobile), ~5 placeholders
- Loaded — table/list with rows
- Empty (no runs at all) — see EmptyState below
- Empty (filters return zero) — table replaced by a small inline message + "Clear filters" button
- Error — error card + retry button + shell-level toast

---

### D. Pagination

**Purpose:** Page through long lists.

**Display:** Row at the bottom of the table.

**Elements:**
- Left: `Showing 1–25 of 124` (range + total count)
- Right: page-number buttons + prev/next chevrons. Page size: 25 rows (TD-configurable; not user-configurable v1).

**Behaviour:**
- Click page number → re-fetch with new `limit_start`.
- `<` / `>` step one page.
- Hidden when total count ≤ page size.
- Page state is session-only (D6) — full reload returns to page 1.

---

### E. EmptyState *(rendered when no runs exist at all)*

**When rendered:** `frappe.client.get_count("Cashew Import Run", filters={})` returns 0 (regardless of current filters).

**Display:** Centered illustration, title, body, primary CTA. Replaces the table+pagination entirely (header + filter bar may stay or hide; designer pick).

**Content:**
- Illustration: line drawing of a stack of papers with a + overlay
- Title: `No imports yet.`
- Body: `Start your first Cashew import by uploading a CSV from the Cashew app's export.`
- Primary button: `+ Start an Import` → `/runs/new`
- Secondary: `Configure mappings →` → `/app/cashew-settings` (back to Desk; out-of-band setup link)

---

## 5. Data sources

### Main fetch

`POST /api/method/frappe.client.get_list`

**Doctype:** `Cashew Import Run`
**Fields requested:**
```
[
  "name",
  "status",
  "company",
  "period_start",
  "period_end",
  "rows_total",
  "rows_valid",
  "rows_failed",
  "rows_posted",
  "rows_skipped",
  "modified",
  "diagnostics_file"
]
```

**Filters (built from FilterBar + search):**
```
[
  ["status", "in", ["Processing", "Failed"]],         // if StatusFilter active
  ["period_start", "<=", "2026-05-24"],               // if PeriodFilter active
  ["period_end",   ">=", "2026-04-25"],
  ["company", "=", "Acme Pvt Ltd"],                   // if CompanyFilter active
  ["name", "like", "%2026%"]                          // if search box has text
]
```

**Order:** `order_by: "<column> <dir>"` from sort state.
**Limit / start:** from pagination.

### Count fetch (for pagination + empty-state)

`POST /api/method/frappe.client.get_count`
**Doctype:** `Cashew Import Run`
**Filters:** same as main fetch (minus pagination).

### Realtime

Subscribe to `Cashew Import Run` doc-level updates per D8. Update individual rows in place.

---

## 6. Page-level states

| State | Look |
|---|---|
| Initial load | Header + filter bar render; table is skeleton rows. |
| Loaded with data | Table renders; pagination shows. |
| Loaded empty (no runs) | EmptyState (E). |
| Loaded empty (filters too narrow) | Table region shows `No runs match these filters` + Clear button. |
| Filter / sort change | Table dims, skeleton overlay for 200ms+, then new data slides in. |
| Error | Table region replaced by error card + retry. Shell toasts the API error. |
| Realtime update | Affected row pulses briefly (border highlight 500ms). |

---

## 7. Responsive notes

| Breakpoint | Layout |
|---|---|
| ≥1024px | Full 10-col table. |
| 768–1023px | Drop columns `Company` + `Posted` (still in row-action menu / kebab → "details"). Table has 8 columns. |
| 640–767px | Drop `Skipped`, `Posted`, `Valid` separately — show a compound "Counts: 124/2/124" cell. 6 columns. |
| <640px | Switch to card list (see C variant). Filter bar collapses into a single "Filters" button that opens a bottom-sheet. |

---

## 8. Accessibility

- Table has proper `<thead>` and `aria-sort` on sorted column header
- Row click = wrapping `<router-link>` over a tr-like region for keyboard nav
- Kebab menu is a proper menu button (aria-haspopup, aria-expanded)
- Search input has visible label (sr-only is fine)
- StatusPills have aria-label with the full status name

---

## 9. Shared components used

| Shared component | Where | See |
|---|---|---|
| `StatusPill` | Status column | `../shared-components.md` |
| `AmountDisplay` | — *(this page doesn't show amounts)* | — |
| `PageHeader` | Section A | `../shared-components.md` |
| `EmptyState` | Section E | `../shared-components.md` |
| `SkeletonBlock` / `SkeletonRow` | Loading state | `../shared-components.md` |

---

## 10. DocType field requests *(open flag from arch UI-phase)*

None for this page. All columns map to existing `Cashew Import Run` fields.

---

## 11. Out of scope (v1)

- Bulk actions on multiple runs (no "select rows" checkbox column). Defer.
- Saved filter presets. D6 — session-only state.
- CSV/Excel export of the list. Defer.
- Re-ordering columns or showing/hiding them. Defer.
- Inline status changes. Defer (only via row-action menu).

---

## 12. Designer notes (Claude Design)

- Table density should be tight but not cramped. Frappe List view feels too dense; Stripe/Linear table feels right.
- Status column is the most-scanned — give the pill enough room to read.
- Counters (Total / Valid / Failed) should align on decimal/right edge for quick scanning. Use tabular-nums.
- Kebab menus should be discoverable on hover (desktop) and always visible on mobile cards.
- The "+ New Import" button is the most important CTA — make it visually heavier than any other on this page.
