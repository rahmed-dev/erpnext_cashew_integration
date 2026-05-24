# Component Mapping — prototype → Vue SFCs

How each prototype component maps to the Vue 3 component tree the build will produce. **Use this as a starting structure** — TD (the architect at component-spec time) may shuffle file layout. The component **IDs** below come from `spec/feature.yaml`'s component list (c001–c011); use those as the canonical names.

## Folder layout

Recommended target structure inside `frontend/src/`:

```
frontend/src/
├── App.vue
├── main.js
├── router.js                         ← createWebHistory; 3 routes
├── boot.js                           ← reads window.boot
├── socket.js                         ← c008 realtime client
├── api/
│   ├── client.js                     ← thin frappe.client.* wrappers (D5.1)
│   └── cashew.js                     ← whitelisted methods (D5.3)
├── stores/                           ← Pinia or composables — TD choice
│   ├── session.js
│   ├── runs.js
│   └── dashboard.js
├── components/
│   ├── shell/                        ← c004
│   │   ├── AppShell.vue
│   │   ├── Sidebar.vue
│   │   ├── AppSwitcher.vue
│   │   ├── PrimaryNav.vue
│   │   ├── UserChip.vue
│   │   ├── RealtimeStatusIndicator.vue
│   │   └── ErrorToastBoundary.vue
│   ├── shared/                       ← shared primitives
│   │   ├── StatusPill.vue
│   │   ├── AmountDisplay.vue
│   │   ├── PageHeader.vue
│   │   ├── EmptyState.vue
│   │   ├── SkeletonBlock.vue
│   │   ├── ConfirmDialog.vue
│   │   ├── DateRange.vue
│   │   ├── DateRangePicker.vue
│   │   ├── KebabMenu.vue
│   │   └── illustrations/            ← EmptyState SVGs
│   ├── dashboard/                    ← c007
│   │   ├── FinanceDashboardPage.vue
│   │   ├── PeriodSelector.vue
│   │   ├── CompanySelector.vue
│   │   ├── BalanceTileGrid.vue
│   │   ├── Tile.vue
│   │   ├── IncomeExpenseChart.vue
│   │   ├── CategoryBreakdownCard.vue
│   │   ├── CategoryList.vue
│   │   ├── RecentImportsStrip.vue
│   │   └── ImportCard.vue
│   ├── imports-list/                 ← c005
│   │   ├── ImportsListPage.vue
│   │   ├── FilterBar.vue
│   │   ├── StatusFilter.vue
│   │   ├── PeriodFilter.vue
│   │   ├── CompanyFilter.vue
│   │   ├── RunsTable.vue
│   │   ├── RunsMobileList.vue
│   │   └── Pagination.vue
│   └── run-workspace/                ← c006 (largest)
│       ├── RunWorkspacePage.vue
│       ├── RunHeader.vue
│       ├── StateStepper.vue
│       ├── sections/
│       │   ├── UploadSection.vue
│       │   ├── PreviewSection.vue
│       │   ├── RowsWorkbench.vue     ← the heart of D11
│       │   └── CompletedSummary.vue
│       └── workbench/
│           ├── WorkbenchToolbar.vue
│           ├── FiltersDropdown.vue
│           ├── ColumnsDropdown.vue
│           ├── ActiveFilterChips.vue
│           ├── RowsTable.vue
│           ├── InlinePartyEdit.vue
│           ├── SelectionFooter.vue
│           ├── ValidationFixModal.vue
│           ├── BulkPartyModal.vue
│           └── registries/
│               ├── columns.js        ← declarative column registry (D11)
│               └── actions.js        ← declarative row-action registry (D11)
```

---

## Shared primitives

| Prototype (`src/ui.jsx`) | Vue SFC | Notes |
|---|---|---|
| `StatusPill` | `shared/StatusPill.vue` | Props: `kind` (`run-status` / `row-validation` / `txn-type` / `row-revert`), `value`, `size` (`sm` / `md`), `pulse` (bool). Status→color map in `spec/shared-components.md` § 1. Always renders value as text + colored bg + optional lucide icon. `aria-label="{kind}: {value}"`. |
| `AmountDisplay` | `shared/AmountDisplay.vue` | Props: `amount` (Number\|null), `currency` (default `'PKR'`), `signed` (bool), `signSource` (Number — drives sign + color when `signed`), `compact` (bool), `tabular` (default `true`), `big` (bool). Uses `Intl.NumberFormat('en-PK', ...)`. Null renders `—` muted. |
| `PageHeader` | `shared/PageHeader.vue` | Props: `title`, `subtitle`, `backRoute`. Slots: `meta`, `actions`. Single row desktop, wraps on mobile (actions move below title). |
| `EmptyState` | `shared/EmptyState.vue` | Props: `illustration` (`empty-list` / `no-data` / `empty-results` / `first-run`), `title`, `body`, `primary` (`{label, action}`), `secondary` (`{label, action}`). Illustrations as SVGs in `shared/illustrations/`. Prototype uses a generic icon-tile placeholder — replace with real line-art. |
| `SkeletonBlock` | `shared/SkeletonBlock.vue` | Props: `shape` (`line` / `block` / `circle` / `row`), `width`, `height`, `lines`. Single shimmer animation, 1.5s loop. |
| `ConfirmDialog` | `shared/ConfirmDialog.vue` | Props: `open` (v-model), `kind` (`info` / `warning` / `danger`), `title`, `body`, `confirmLabel`, `cancelLabel`, `confirming`. Wrap frappe-ui `<Dialog>`. Focus-trapped, Esc cancels. |
| `DateRange` | `shared/DateRange.vue` + `DateRangePicker.vue` | Display + editable variants. See `spec/shared-components.md` § 7. |
| `KebabMenu` | `shared/KebabMenu.vue` | Props: `items` (array of `{label, icon, action, disabled, danger, divider}`), `align`. Wrap frappe-ui `<Dropdown>`. |
| `Tile` (dashboard) | `dashboard/Tile.vue` | Renders icon chip, label, big amount, delta chip. Props: `icon`, `label`, `amount`, `priorAmount`, `accentColor`, `currency`. |
| `Icon` | use `lucide-vue-next` directly | No custom Icon component — import per-icon in each SFC. |

### frappe-ui primitives — use directly (no wrapper)

Per `spec/shared-components.md` § 11:

| Primitive | Used for |
|---|---|
| `<Autocomplete>` | Every Link selector. Pass `reference_doctype` + `reference_fieldname` (D5 rule 2). |
| `<Button>` | Every button — `variant: solid/subtle/ghost/outline`, `theme: gray/blue/red`. The prototype's `.cs-btn-primary` = `<Button variant="solid" theme="blue">`. |
| `<Input>` | Text inputs (search, custom amount). |
| `<Select>` | Enum selects when not styled as a chip. |
| `<Tooltip>` | Column header tooltips, truncated text expansion. |
| `<Dialog>` | Wrapper for `ConfirmDialog`, `ValidationFixModal`, `BulkPartyModal`. |
| `<Dropdown>` | Wrapper for `KebabMenu`, app switcher, user chip, filter chips. |

---

## Shell (c004)

`design-reference/src/Shell.jsx` → `components/shell/*`

| Prototype | Vue SFC | Notes |
|---|---|---|
| `Shell` (root) | `AppShell.vue` | Two-column layout. Props: none — reads route from `vue-router`, session from store, realtime state from `useRealtime()`. Mobile: sidebar becomes overlay drawer. |
| `AppSwitcher` | `AppSwitcher.vue` | Cashew logo + name + chevron-down. Dropdown items: Cashew (active), Back to Desk → `/app`. Future apps append here. Use `<Dropdown>`. |
| `PrimaryNav` + `SidebarLink` | `PrimaryNav.vue` | Vertical list of `<router-link>`s. Active state via `:exact-active-class` for `/`, prefix-match for `/runs`. 2px accent stripe on left edge of active item. |
| `UserChip` | `UserChip.vue` | Avatar + name + chevron, opens menu (Settings / Help / Sign out — see `spec/shell.md` § 3). Reads `window.boot.session_user`. |
| `RealtimeDot` | `RealtimeStatusIndicator.vue` | 4 states: connected (green dot, "Live") / reconnecting (amber pulse, "Reconnecting…") / polling (grey, "Polling") / disconnected (red, "Offline"). Reads from `useRealtime()` composable. |
| (toast region — invisible) | `ErrorToastBoundary.vue` | Intercepts every `/api/*` error (D5.c). Stacks toasts bottom-right. `aria-live="polite"`. Expose `useToast()` composable for pages to emit non-error toasts. |

---

## Finance Dashboard (c007)

`design-reference/src/Dashboard.jsx` → `components/dashboard/*`

| Prototype | Vue SFC | Notes |
|---|---|---|
| `FinanceDashboard` | `FinanceDashboardPage.vue` | Top-level page. Fetches `dashboard_summary` (c009) on mount + on filter change. Subscribes to `Cashew Import Run` `doc_update`, debounces re-fetch ~2s. |
| `PeriodSelector` | `PeriodSelector.vue` | Pill dropdown with 6 presets + Custom Range. Emits `update:modelValue` with `{start, end, preset}`. Default `'This Month'`. Session-only state (D6). |
| (conditional company picker) | `CompanySelector.vue` | Only renders when user has >1 company. frappe-ui `<Autocomplete reference_doctype="Company">`. |
| (4-tile grid) | `BalanceTileGrid.vue` | Grid wrapper; renders 4 `<Tile>`s. |
| `Tile` | `Tile.vue` | One headline number with icon chip, label, value, prior-period delta. Skeleton variant for loading. |
| `IncomeExpenseChart` + `DonutChart` + `BarChart` | `IncomeExpenseChart.vue` | Chart card. **TD picks chart library** — frappe-ui chart wrapper if it covers donut + bar; else chart.js. Prototype's hand-rolled SVG is only for visual reference. Donut variant has Net amount in center. |
| `CategoryBreakdownCard` + `CategoryList` | `CategoryBreakdownCard.vue` | Two stacked sections (Income / Expense), top 5 per side, with horizontal mini-bar per row. |
| `RecentImportsStrip` + `ImportCard` | `RecentImportsStrip.vue` + `ImportCard.vue` | Horizontal scroll of compact import cards. Each card is a `<router-link to="/runs/:name">`. |
| (when zero data) | inline empty state via `<EmptyState>` | Renders when `dashboard_summary` returns all zeros + no recent runs. |

---

## Imports List (c005)

`design-reference/src/ImportsList.jsx` → `components/imports-list/*`

| Prototype | Vue SFC | Notes |
|---|---|---|
| `ImportsList` | `ImportsListPage.vue` | Top-level. Calls `frappe.client.get_list('Cashew Import Run', ...)` per D5 rule 1. Realtime subscription updates rows in place. |
| `StatusFilterDD` | `StatusFilter.vue` | Multi-select dropdown with checkbox per status + "Select all" / "Clear". |
| (period chip) | `PeriodFilter.vue` | Same options as dashboard `PeriodSelector` (plus `Any`). Default `Any`. |
| (company chip) | `CompanyFilter.vue` | frappe-ui `<Autocomplete>` styled as chip. Hidden if user has 1 company. |
| `FilterChip` | inline in `FilterBar.vue` | Generic chip used by Period / Company filters. |
| (search input) | inline `<Input>` with search icon | 250ms debounce; filter via `name like %term%` server-side. |
| `Th` (sortable header) | inline `<SortableTh>` in `RunsTable.vue` | Click toggles asc/desc. Default sort: `modified desc`. v1 sortable: `status`, `period_start`, `modified`. |
| `RunsTable` | `RunsTable.vue` | Desktop table. Row click → `/runs/:name`. Kebab opens action menu. Columns drop on smaller breakpoints (see `spec/pages/imports-list.md` § 7). |
| `RunMobileCard` | `RunsMobileList.vue` | Used at `<sm` breakpoint instead of the table. |
| `KebabMenu` (per-row) | `shared/KebabMenu.vue` | Open in workspace · Open in Desk · Download diagnostics · Revert · Cancel. Conditional per `status`. |
| (pagination row) | `Pagination.vue` | 25 per page. Hidden when total ≤ page size. Session-only (page state resets on reload). |

---

## Run Workspace (c006 — largest)

`design-reference/src/Workspace.jsx` → `components/run-workspace/*`

Single page component; **`/runs/new` and `/runs/:run_name` both resolve here**. State-driven sections render based on `run.status`.

### Always present
| Prototype | Vue SFC | Notes |
|---|---|---|
| `RunHeader` | `RunHeader.vue` | 2 rows: identity (back, name, status, live tag, open-in-Desk) + metadata + state-dependent actions. Actions disable + show inline spinner during API call. See `spec/pages/run-workspace.md` § 4.A for the full action table. |
| `StateStepper` | `StateStepper.vue` | 4-step indicator. Pure progress, not clickable. Steps: Upload (Draft) · Preview (Parsed) · Workbench (Validated/Queued/Processing) · Done (terminal). |
| `ConfirmModal` | `shared/ConfirmDialog.vue` | Used for Queue / Cancel / Revert / Discard confirmations. |

### State-driven sections
| Status | Prototype | Vue SFC |
|---|---|---|
| `Draft` (or `/runs/new`) | `UploadSection` | `sections/UploadSection.vue` — CompanyPicker, CsvDropzone, OptionalConfigDisclosure, PrimaryActions |
| `Parsed` | `PreviewSection` | `sections/PreviewSection.vue` — ParseStatsBar (`StatCell` × 7), read-only PreviewTable |
| `Validated` / `Queued` / `Processing` | `RowsWorkbench` | `sections/RowsWorkbench.vue` — toolbar, active filter chips, RowsTable, SelectionFooter, ValidationFixModal, BulkPartyModal |
| Terminal states | `CompletedSummary` | `sections/CompletedSummary.vue` — ResultBanner, CountsGrid, PostedBreakdown, read-only RowsTable, DangerZone |

### Workbench internals (`workbench/*`)

| Prototype | Vue SFC | Notes |
|---|---|---|
| `WorkbenchToolbar` (inline in `RowsWorkbench`) | `WorkbenchToolbar.vue` | Search + Filters dropdown + Columns dropdown + Bulk actions dropdown + Re-validate button. |
| `FILTERS_FACETS` constant | `workbench/registries/filters.js` + `FiltersDropdown.vue` | **Declarative filter registry (D11).** Each facet: `{key, label, type: 'select'|'tri-state'|'toggle', options}`. Adding a facet = appending to the registry. |
| (active filter chip strip) | `ActiveFilterChips.vue` | One removable chip per active value + "Clear all" link. |
| (column presets — see spec § 5.III.1) | `workbench/registries/columns.js` + `ColumnsDropdown.vue` | **Declarative column registry (D11).** Each column: `{key, label, visibleInPresets, type, formatter}`. Presets: `compact`, `validation-focused`, `posting-focused`, `wide`. |
| `RowsTable` (inline) | `RowsTable.vue` | Sticky header. Sticky `Sr` + `Sel` columns. Horizontal scroll for wide column sets. Row click → opens `InlineRowDrawer` (TD-time decision: use this or stick with double-click party + per-row kebab). Color cues per spec: error left-border red, posted green, duplicate faded, skipped 60% opacity. |
| `InlinePartyEdit` (inline in RowsTable) | `InlinePartyEdit.vue` | Activated by double-click on Party cell. Party Type select + frappe-ui `<Autocomplete>` with `reference_doctype` dynamic. Tab moves between, Enter saves, Esc cancels. |
| `ValidationFixModal` | `ValidationFixModal.vue` | Per-row error fixer. Conditional fields by `validation_error_code` (`NO_ACCOUNT_MAP` → resolved_account; `MISSING_PARTY` → party_type + party; `NO_EXTERNAL_ACCT` → external_account). Save calls `row_explorer_revalidate(run_name, [row_idx])`. Modal stays open on persistent error. |
| `BulkPartyModal` | `BulkPartyModal.vue` | Party type + party for N selected rows. Calls `row_explorer_set_party(run_name, indices, type, party)`. |
| `SelectionFooter` | `SelectionFooter.vue` | Sticky bottom pill. Shows count + Set party / Re-validate / Clear actions. Animates in/out. |
| **Bulk actions registry** | `workbench/registries/actions.js` | **Declarative bulk-action registry (D11).** Each action: `{key, label, icon, modal, handler}`. v1 has Set party + Re-validate selected. Future actions plug in here. |

### Completed summary internals
| Prototype | Vue SFC | Notes |
|---|---|---|
| `ResultBanner` (inline) | inline in `CompletedSummary.vue` | One of 6 looks by status (Completed/Failed/Cancelled/Reverting/Reverted/Revert-Failed). |
| `CountsGrid` (inline) | inline | Same `StatCell`s as preview, but post-run values. |
| `PostedBreakdown` (inline) | `PostedBreakdown.vue` | List w/ mini-bars per posted doctype. Optional click → filter the RowsTable below. |
| Read-only `RowsTable` | reuse `RowsTable.vue` | Pass `mode="readonly"` prop. Default filter: `posted = failed/reverted`. Toggle "Show all". |
| `DangerZone` (inline) | inline in `CompletedSummary.vue` | Red-tinted card with Revert + Download diagnostics. Only when `status = Completed`. Confirm dialog before Revert. |

---

## Alternates (exploratory)

`design-reference/src/Alternates.jsx` → **not part of the build deliverable.** Two opinionated proposals for future discussion:

- `DashboardAlt` — Linear-style single-bar stat row + ledger-style category P&L table.
- `WorkbenchSplitAlt` — permanent collapsible row detail drawer on the right (faster fix-row UX than modals; collapses to give the table full width).

If either gets promoted to scope, it becomes a feature ticket.

---

## Realtime client (c008)

`spec/feature.yaml` and `spec/arch-decisions.md` D8.

Single composable: `useRealtime()`. Returns reactive `{ state, isConnected }` + lets pages subscribe:

```js
// In RunWorkspacePage.vue
const { subscribeDoc } = useRealtime();
const unsub = subscribeDoc('Cashew Import Run', route.params.run_name, (event) => {
  // event has the updated doc fields — merge into local state
});
onUnmounted(unsub);
```

Internal: wraps `socket.io-client`. Subscribes to Frappe's `doc_update` channel. Falls back to polling `get_run_progress(run_name)` every 30s on permanent socket loss. The connection-state composable feeds `RealtimeStatusIndicator.vue` in the sidebar.

---

## API mapping

| UI action | Endpoint | Rule |
|---|---|---|
| Imports list fetch | `frappe.client.get_list('Cashew Import Run', ...)` | D5.1 (read) |
| Imports list count (pagination + empty-state) | `frappe.client.get_count('Cashew Import Run', ...)` | D5.1 |
| Run detail fetch (on mount) | `frappe.client.get_doc('Cashew Import Run', name)` | D5.1 |
| Dashboard summary | `cashew_integration.api.dashboard_summary(period_start?, period_end?, company?)` | D5.4 (aggregate, c009) |
| Parse action | `cashew_integration.api.parse_and_preview(run_name)` | D5.3 (write) |
| Validate action | `cashew_integration.api.validate_import(run_name)` | D5.3 |
| Queue action | `cashew_integration.api.queue_run(run_name)` | D5.3 |
| Cancel action | `cashew_integration.api.cancel_run(run_name)` | D5.3 |
| Revert action | `cashew_integration.api.revert_run(run_name)` | D5.3 |
| Set row party (inline + bulk) | `cashew_integration.api.row_explorer_set_party(run_name, row_indices, party_type, party)` | D5.3 |
| Re-validate rows | `cashew_integration.api.row_explorer_revalidate(run_name, row_indices)` | D5.3 |
| Poll progress (socket fallback) | `cashew_integration.api.get_run_progress(run_name)` | D5.4 |
| Delete draft | `frappe.client.delete('Cashew Import Run', name)` | D5.1 |
| Link selectors (Company, Customer, Supplier, Account) | `frappe-ui <Autocomplete reference_doctype reference_fieldname>` | D5.2 |
| File upload (Upload section) | `/api/method/upload_file` with `is_private=1` | Frappe standard |

Every `cashew_integration.api.*` whitelisted method must call `frappe.has_permission(...)` at entry (c010 audit confirms this for existing endpoints).

---

## Boot data

`cashew_integration/www/cashew.py` (c002) injects via Jinja:

```py
context.boot = {
  "csrf_token":      frappe.sessions.get_csrf_token(),
  "session_user":    frappe.session.user,
  "sysdefaults":     frappe.defaults.get_defaults(),
  "default_company": frappe.defaults.get_user_default("Company"),
  "default_currency": frappe.db.get_default("currency"),
  # period defaults: TD decides — likely first-of-current-month → today
}
```

Read in `boot.js` and stash on session store. Components consume via store, not `window.boot` directly (cleaner for testing).
