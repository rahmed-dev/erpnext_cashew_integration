# c005 — imports-list-page

> **Type:** ui-page
> **Depends on:** c004 (router + shell + composables), c013 (no direct dep, but
> StatusPill enums reference run states)
> **Arch refs:** D5 (hybrid API: reads via `frappe.client.*`, Link selectors via
> frappe-ui `<Autocomplete>`), D6 (session-only state, no localStorage), D8
> (realtime subscription)
> **Design brief:** `.fb/ui/pages/imports-list.md` (source of truth for visual
> shape, columns, copy, breakpoints, designer notes)
> **React reference:** `design_handoff_f010_cashew_spa/design-reference/src/ImportsList.jsx`

---

## Overview

Imports List is the operator's home — a searchable, filterable, paginated
table of every Cashew Import Run, plus the entry point for "+ New Import".
Mounts at `/runs` (router defined in c004). Realtime: row updates in place
on `Cashew Import Run` `doc_update`; new runs appear at the top with a
500ms highlight pulse.

This spec covers the Vue page + its sub-components, the two `frappe.client.*`
calls, the filter / sort / pagination state model (all in-memory per D6),
and the realtime hookup (consumes c008's `subscribeList` helper).

---

## Routes (already declared in c004)

- `/runs` → `ImportsListPage.vue`. Sidebar nav item "Imports".
- "+ New Import" button routes to `/runs/new` (c006).
- Row click routes to `/runs/:run_name` (c006).

---

## File tree

```
frontend/src/pages/
  ImportsList.vue                    # the page (replaces c004 stub)

frontend/src/components/imports-list/
  FilterBar.vue                      # status + period + company chips + search
  StatusFilter.vue                   # multi-select dropdown (4 status values)
  PeriodFilter.vue                   # shared with dashboard (see c007); imported
  CompanyFilter.vue                  # frappe-ui Autocomplete, chip style
  RunsTable.vue                      # desktop table (>=640px)
  RunsCardList.vue                   # mobile card list (<640px)
  RunRow.vue                         # single <tr> for RunsTable
  RunCard.vue                        # single card for RunsCardList
  RowKebabMenu.vue                   # dropdown for row actions
  Pagination.vue                     # local to this page; shared if needed later
  EmptyAllRuns.vue                   # zero-runs-anywhere state
  EmptyFilterMiss.vue                # zero-runs-for-current-filters state
```

`PeriodFilter.vue` is authored by c007 (used on dashboard first); c005 imports
it. If c005 ships before c007, author it under
`frontend/src/components/shared/PeriodFilter.vue` and c007 imports from there.

---

## State model (all in-memory; D6 binding)

`ImportsList.vue` owns one `state` ref with:

```js
const state = reactive({
  filters: {
    status: [],              // multi-select; [] = all
    period: 'any',           // 'any' | 'this-month' | 'last-month' | 'last-3-months' | 'custom'
    period_range: null,      // { start: 'YYYY-MM-DD', end: 'YYYY-MM-DD' } when period === 'custom'
    company: null,           // company name or null
    search: '',              // raw query, before debounce
  },
  sort: { column: 'modified', dir: 'desc' },
  page: { start: 0, length: 25 },
  // results
  rows: [],
  total: 0,
  loading: true,
  error: null,
})
```

Page size `25` is a constant at the top of the file
(`const PAGE_SIZE = 25`); not user-configurable v1.

Search input is bound to `state.filters.search` directly; a debounced
`watch` triggers re-fetch (250ms). All other filters re-fetch on change
immediately.

Filter / sort change → reset `page.start = 0`. Page change → keep filters.

Never write any of this to `localStorage` or `sessionStorage`.

---

## Data layer

Two `frappe-ui` `createResource` instances declared at top of `setup()`:

```js
import { createResource } from 'frappe-ui'

const runsResource = createResource({
  url: 'frappe.client.get_list',
  cache: false,
  makeParams: () => buildGetListParams(state),
})

const countResource = createResource({
  url: 'frappe.client.get_count',
  cache: false,
  makeParams: () => buildCountParams(state),
})
```

`runsResource.data` → `state.rows`. `countResource.data` → `state.total`.
Both call `reload()` on filter / sort / page changes.

**`buildGetListParams(state)`** returns the `get_list` arg shape:

```js
{
  doctype: 'Cashew Import Run',
  fields: [
    'name', 'status', 'company',
    'period_start', 'period_end',
    'rows_total', 'rows_valid', 'rows_failed', 'rows_posted', 'rows_skipped',
    'modified', 'diagnostics_file',
  ],
  filters: buildFilterArray(state.filters),
  order_by: `${state.sort.column} ${state.sort.dir}`,
  limit_start: state.page.start,
  limit_page_length: state.page.length,
}
```

**`buildFilterArray(filters)`** assembles the frappe filter list:

```js
function buildFilterArray(f) {
  const out = []
  if (f.status?.length) out.push(['status', 'in', f.status])
  const range = resolvePeriodRange(f.period, f.period_range)
  if (range) {
    out.push(['period_start', '<=', range.end])
    out.push(['period_end',   '>=', range.start])
  }
  if (f.company) out.push(['company', '=', f.company])
  const term = f.search?.trim()
  if (term) out.push(['name', 'like', `%${term}%`])
  return out
}
```

**`resolvePeriodRange(period, range)`** — pure function in `src/utils/period.js`,
also used by dashboard (c007). Returns `{ start, end }` ISO date strings or
`null` for `'any'`. Uses `useDefaultPeriod()` (c004 boot accessor) for first-of-
month math.

`buildCountParams` is identical to `buildGetListParams` minus `fields` / `order_by`
/ `limit_*`.

---

## Components

### `ImportsList.vue` — top-level

```vue
<template>
  <div class="px-4 py-6 max-w-7xl mx-auto">
    <PageHeader title="Imports">
      <template #actions>
        <Button variant="solid" theme="accent" iconLeft="plus" @click="$router.push('/runs/new')">
          New Import
        </Button>
      </template>
    </PageHeader>

    <FilterBar v-model:filters="state.filters" />

    <!-- Empty: zero runs anywhere -->
    <EmptyAllRuns v-if="!state.loading && state.total === 0 && !hasActiveFilters" />

    <!-- Empty: filters too narrow -->
    <EmptyFilterMiss
      v-else-if="!state.loading && state.rows.length === 0 && hasActiveFilters"
      @clear="clearFilters"
    />

    <!-- Table or card list -->
    <component
      v-else
      :is="isMobile ? RunsCardList : RunsTable"
      :rows="state.rows"
      :loading="state.loading"
      :sort="state.sort"
      @sort="onSort"
      @open="row => $router.push(`/runs/${row.name}`)"
      @action="onRowAction"
    />

    <Pagination
      v-if="state.total > PAGE_SIZE"
      :start="state.page.start"
      :length="PAGE_SIZE"
      :total="state.total"
      @page="onPage"
    />
  </div>
</template>
```

Setup logic:
- Imports `useIsMobile()` from `src/state/useIsMobile.js` (c004) — drives
  table-vs-card swap at the 640px breakpoint.
- Imports `subscribeList` from `src/realtime.js` (c008) — subscribes to
  `Cashew Import Run` list-level `doc_update`. On event:
  - If event run's `name` matches a row in `state.rows`: patch row in place;
    set `pulseMap[name] = Date.now() + 500` to drive the highlight.
  - If event run's `name` NOT in `state.rows` AND filters pass (cheap client
    check) AND we're on page 1: prepend + drop last row (keep `length`
    stable) + pulse.
  - Always: trigger `countResource.reload()` (debounced 1s) so the pagination
    total stays current.
- `onMounted` triggers `runsResource.reload()` + `countResource.reload()`.
- `onBeforeUnmount` calls the subscription's unsubscribe fn.

Computed: `hasActiveFilters` returns true when any filter is set or search
non-empty.

### `FilterBar.vue`

```vue
<template>
  <div class="flex flex-wrap items-center gap-2 mb-4">
    <StatusFilter v-model="filters.status" />
    <PeriodFilter v-model:period="filters.period" v-model:range="filters.period_range" />
    <CompanyFilter v-if="showCompany" v-model="filters.company" />
    <Input
      v-model="filters.search"
      placeholder="Search by run name…"
      :iconLeft="SearchIcon"
      class="ml-auto w-64"
    />
    <button
      v-if="hasAny"
      class="text-sm text-ink-3 underline ml-2"
      @click="$emit('clear')"
    >
      Clear filters
    </button>
  </div>
</template>
```

Mobile (`isMobile === true`): collapse all chips into a single
`<Button>Filters (n)</Button>` that opens a `<Dialog>` (frappe-ui) used as a
bottom sheet (`positionClasses` overridden to slide-from-bottom on mobile).

`showCompany`: read `useSysDefaults().default_company` AND the count of
companies the user can see. Hide the chip if they have one company
(`frappe.client.get_count('Company', filters={ disabled: 0 })` cached at
page mount). If the user picks a different company in the future, the
chip auto-appears — re-checked on page mount only (D6 — no persistence).

### `StatusFilter.vue`

frappe-ui `<Dropdown>` with checkboxes for each of the 4 enum kinds.
Status values (from `Cashew Import Run.json` — verify on dev start):
`Draft`, `Parsed`, `Validating`, `Validated`, `Queued`, `Processing`,
`Completed`, `Failed`, `Reverting`, `Reverted`, `Revert-Failed`, `Cancelled`.

The brief asks the dropdown to read clean — group into:
- **In flight**: Queued, Processing, Validating, Reverting
- **Attention**: Failed, Revert-Failed
- **Terminal**: Completed, Reverted, Cancelled
- **Draft**: Draft, Parsed, Validated

Group labels are headings; clicking the heading toggles the whole group.

### `PeriodFilter.vue`

Shared component. Options: `Any` (default), `This month`, `Last month`,
`Last 3 months`, `Custom…`. Selecting `Custom…` opens a date-range
picker dialog (frappe-ui `<DateRangePicker>` if available, else two
`<Input type="date">` in a `<Dialog>`).

### `CompanyFilter.vue`

```vue
<Autocomplete
  v-model="company"
  reference_doctype="Cashew Import Run"
  reference_fieldname="company"
  placeholder="Company"
  class="w-48"
/>
```

D5 rule 2 — `reference_doctype` + `reference_fieldname` so any registered
`get_query` for `Cashew Import Run.company` honors automatically.

### `RunsTable.vue`

Standard `<table>` with sticky header, tabular-nums on count columns,
right-aligned counts. Sort handled via header click: emits
`@sort="{ column, dir }"`. Columns drop per breakpoint:

| Breakpoint | Drop |
|---|---|
| `>= 1024` | none (10 cols) |
| `768–1023` | `company`, `rows_posted` (8 cols) |
| `640–767` | `rows_skipped`, `rows_posted`, `rows_valid` separately → compound `counts` cell (6 cols) |

Use Tailwind responsive utilities (`hidden md:table-cell`, etc.) — no
script-driven column toggling.

Rows: `<RunRow :row="row" :pulse="pulseMap[row.name]" />`. `pulse`
applies a `border-accent animate-pulse-once` class for 500ms.

### `RunsCardList.vue`

Replaces table at `< 640`. Card shape per design brief section 4C.
Realtime pulse same as row pulse (`border-accent animate-pulse-once`).

### `RowKebabMenu.vue`

frappe-ui `<Dropdown>` triggered by a kebab icon. Items (per the design
brief 4C):

```js
const items = computed(() => [
  { label: 'Open in workspace', icon: 'arrow-right', onClick: () => router.push(`/runs/${row.name}`) },
  { label: 'Open Desk form (legacy)', icon: 'external-link', onClick: () => window.open(`/app/cashew-import-run/${row.name}`, '_blank') },
  row.diagnostics_file && ['Completed', 'Failed', 'Revert-Failed'].includes(row.status) && {
    label: 'Download diagnostics CSV',
    icon: 'download',
    onClick: () => window.open(row.diagnostics_file, '_blank'),
  },
  row.status === 'Completed' && {
    label: 'Revert',
    icon: 'rotate-ccw',
    danger: true,
    onClick: () => confirmAndCall('revert_run', row.name),
  },
  ['Queued', 'Processing'].includes(row.status) && {
    label: 'Cancel',
    icon: 'x-octagon',
    danger: true,
    onClick: () => confirmAndCall('cancel_run', row.name),
  },
].filter(Boolean))
```

`confirmAndCall(method, run_name)` opens a `<ConfirmDialog>` and on confirm
posts to `cashew_integration.api.{method}`. Errors → frappe-ui Toast
(c004 error interceptor handles 401/403/5xx; this just rethrows). Success
→ Toast `"Revert queued"` / `"Cancellation requested"`; realtime updates
the row.

### `Pagination.vue`

Per brief section 4D. Hidden when `total <= length`. Page numbers cap at
7 buttons with `…` ellipsis when needed. Prev / next chevrons.

### `EmptyAllRuns.vue` / `EmptyFilterMiss.vue`

Per brief section 4E + 6. `EmptyAllRuns` uses a lucide `file-plus` icon
in a light circle (no commissioned illustration v1; ship the lucide
glyph, swap later if designer commissions one).

---

## Shared components consumed

From `frappe-ui`:
- `Button`, `Input`, `Dropdown`, `Autocomplete`, `Dialog`, `Toast`

From `src/components/shared/`:
- `StatusPill.vue` — authored alongside c005 (also used by c006 / c007 /
  RunCard). Maps status string → pill color + label.
  Authored here; file path `frontend/src/components/shared/StatusPill.vue`.

---

## Realtime contract with c008

c008 will export `subscribeList(doctype, callback)` and
`subscribeDoc(doctype, name, callback)`. c005 uses `subscribeList`:

```js
import { subscribeList } from '@/realtime'

let unsub
onMounted(() => {
  unsub = subscribeList('Cashew Import Run', onRunChange)
})
onBeforeUnmount(() => unsub?.())
```

Until c008 ships, `src/realtime.js` exports stubs that return a no-op
unsubscribe. Page works without realtime — manual refresh / filter
change re-fetches.

---

## Acceptance

- [ ] `/runs` renders header + filter bar + table on initial load.
- [ ] Skeleton state on first fetch (~5 skeleton rows).
- [ ] Empty-no-runs state renders when no runs exist + no filters set.
- [ ] Empty-filter-miss state renders when filters return 0 rows.
- [ ] Status filter multi-select, period filter, company filter (when
      visible), and search box all trigger a re-fetch.
- [ ] Search box debounces at 250ms.
- [ ] Sort by Status / Period / Updated works; default `modified desc`.
- [ ] Pagination shows when `total > 25`; hidden when `total <= 25`.
- [ ] Page change preserves filters / sort.
- [ ] Filter / sort change resets page to 1.
- [ ] Row click navigates to `/runs/:name`.
- [ ] Kebab menu items conditional on `status` + `diagnostics_file` per
      brief table.
- [ ] `+ New Import` button navigates to `/runs/new`.
- [ ] Mobile (`< 640px`): card list renders instead of table; filter bar
      collapses to a `Filters` button opening a bottom-sheet dialog.
- [ ] Realtime updates patch an existing row in place; new runs prepend
      to page 1 (only) with a 500ms highlight pulse.
- [ ] Nothing under `state` is persisted to `localStorage` /
      `sessionStorage` (grep `src/pages/ImportsList.vue` + everything
      under `src/components/imports-list/` for those strings; must be
      zero hits).

---

## TD calls inside arch envelope (not surfacing)

- Page size 25 — picked over 50/100 because mobile cards get unwieldy
  beyond ~25 in one scroll. Constant at top of file; trivial to change.
- StatusFilter grouping (In flight / Attention / Terminal / Draft) — UX
  call to make the 12-status dropdown readable. Behavioral grouping
  shadows the actual enum; brief doesn't prescribe groups.
- `name like %term%` search over a custom whitelisted endpoint — the
  list is small (a few hundred runs at most for any reasonable
  cashew_integration deployment); index-driven `like` against `name`
  is fast. Revisit if cardinality grows.
- Realtime debounce on count refresh (1s) — avoids hammering get_count
  during burst worker updates.
- Pulse via CSS `animate-pulse-once` keyframe — needs adding to
  `tailwind.config.js` (one keyframe + one animation entry). Implementer
  detail; defer to Dev.

---

## Open items (handed off)

- **`animate-pulse-once` keyframe + Tailwind config entry** — Dev to add
  during c005 implementation. Strawman: `@keyframes pulse-once { 0%,100% { border-color: transparent } 50% { border-color: var(--cs-accent) } }`.
- **`DateRangePicker` availability in frappe-ui** — if absent at install
  time, ship two `<Input type="date">` in a `<Dialog>`. Verify on first
  yarn install.
- **Company auto-hide threshold** — chip hidden when user sees one
  company. If multi-company users want to "lock to default" instead,
  add a Settings toggle (c012 candidate; not in scope for c005).
- **Diagnostics URL CORS** — `window.open(diagnostics_file, '_blank')`
  assumes the URL is same-origin file path served by Frappe. Verify
  for File doctype private-file URLs (`/private/files/...`) — if a
  signed URL is required, use `frappe.utils.file_manager.get_file_url`.
