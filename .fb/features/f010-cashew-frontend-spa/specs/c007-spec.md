# c007 — finance-dashboard-page

> **Type:** ui-page
> **Depends on:** c004 (router + shell + boot accessors), c009 (dashboard_summary)
> **Arch refs:** D9 (GL-derived finance overview), D5 (hybrid API; single
> aggregate endpoint), D6 (session-only state), D8 (realtime debounce 2s)
> **Design brief:** `.fb/ui/pages/finance-dashboard.md`
> **React reference:** `design_handoff_f010_cashew_spa/design-reference/src/Dashboard.jsx`

---

## Overview

SPA landing page (`/`). One API call (`cashew_integration.api.dashboard_summary`)
hydrates the whole page. Operator/manager sees this between imports.

Layout: PageHeader + BalanceTileGrid + (IncomeExpenseChart | CategoryBreakdownCard)
+ RecentImportsStrip. Renders DashboardEmptyState instead when the period
has no GL data AND no recent runs.

**Locked TD decisions:**
- **TD-1 Chart library = frappe-ui's chart wrapper** (`<DonutChart>` /
  `<BarChart>` if exported; verify on first install). If frappe-ui v0.1.x
  doesn't export a usable wrapper, fall back to `chart.js` via
  `vue-chartjs`. Hand-rolled SVG (React prototype) NOT shipped.
- **TD-2 Period presets are 6** (this month, last month, last 30, last 90,
  this fiscal year, custom). Default = `This Month`. `useDefaultPeriod()`
  (boot, c004) seeds the first render; PeriodSelector takes over after.
- **TD-3 Currency formatting** uses `Intl.NumberFormat(locale,
  { style: 'currency', currency: data.currency })`. Locale = browser
  default (`navigator.language`); zero localStorage. Shared component
  `AmountDisplay.vue`.
- **TD-4 Empty-state test** = `income_total === 0 && expense_total === 0
  && Object.values(balance_tiles).every(t => t.amount === 0) &&
  recent_runs.length === 0`. Exact predicate; not "any zero".

---

## File tree

```
frontend/src/pages/
  FinanceDashboard.vue                # replaces c004 stub; mounts at "/"

frontend/src/components/finance-dashboard/
  PageHeader.vue                      # title + PeriodSelector + CompanySelector
  PeriodSelector.vue                  # SHARED — also imported by c005 ImportsList
  CompanySelector.vue                 # frappe-ui Autocomplete; renders only when >1 company
  BalanceTileGrid.vue                 # 4-tile grid wrapper
  BalanceTile.vue                     # one tile (icon + label + amount + delta)
  IncomeExpenseChart.vue              # donut OR bar — single component, swap via prop
  CategoryBreakdownCard.vue           # two stacked sections (Income / Expense)
  CategoryBreakdownList.vue           # one side of the breakdown (5 rows + mini-bars)
  RecentImportsStrip.vue              # horizontal scroll of compact import cards
  ImportCard.vue                      # one card
  DashboardEmptyState.vue             # zero-data fallback

frontend/src/components/shared/
  AmountDisplay.vue                   # NEW — currency formatter (shared across pages)
  DeltaChip.vue                       # NEW — green/red ↑↓ delta
  PageHeader.vue                      # NEW — shared (also used by c005)
  EmptyState.vue                      # NEW — generic empty state primitive
  SkeletonBlock.vue                   # NEW — shimmer placeholder primitive
```

`PeriodSelector.vue` lives under `finance-dashboard/` because that's where
its UX is most central, but it's exported via `src/components/shared/index.js`
re-export so c005 imports cleanly.

---

## Data layer

Single `createResource` for the whole page:

```js
import { createResource } from 'frappe-ui'

const summary = createResource({
  url: 'cashew_integration.api.dashboard_summary',
  cache: false,
  makeParams: () => ({
    period_start: state.period.start,
    period_end:   state.period.end,
    company:      state.company,
  }),
  onError: (e) => {
    // c004's installErrorInterceptors already toasted via the global path;
    // here we only flip the page error flag so the section error UIs show.
    state.lastError = e?.message || 'Unknown error'
  },
})
```

State (all session-only per D6):

```js
const state = reactive({
  period: useDefaultPeriod(),    // { start, end } from boot, c004
  period_preset: 'this-month',
  company: useCashewSettings().value.default_company
            || useSysDefaults().value.default_company
            || null,
  showCompanySelector: false,    // computed at mount
  lastError: null,
})
```

`showCompanySelector` set in `onMounted` via
`frappe.client.get_count('Company', { disabled: 0 })`; if > 1, true.

Re-fetch triggers (single resource — Vue Router 4 reactivity drives
`makeParams`):
- `state.period` change → `summary.reload()`
- `state.company` change → `summary.reload()`

Realtime (c008 sets this up):

```js
import { subscribeList } from '@/realtime'
import { useDebounceFn } from '@vueuse/core'  // see open items

const debouncedReload = useDebounceFn(() => summary.reload(), 2000)
let unsub
onMounted(() => {
  unsub = subscribeList('Cashew Import Run', debouncedReload)
})
onBeforeUnmount(() => unsub?.())
```

(If `@vueuse/core` not already pulled by frappe-ui, ship a tiny inline
debounce — see open items.)

---

## Component sketches

### `FinanceDashboard.vue` (page root)

```vue
<template>
  <div class="px-4 py-6 max-w-7xl mx-auto">
    <PageHeader title="Finance Dashboard">
      <template #controls>
        <PeriodSelector
          v-model:period="state.period"
          v-model:preset="state.period_preset"
        />
        <CompanySelector
          v-if="state.showCompanySelector"
          v-model="state.company"
        />
      </template>
    </PageHeader>

    <template v-if="summary.loading && !summary.data">
      <BalanceTileGrid :data="null" />
      <div class="grid md:grid-cols-2 gap-4 mt-4">
        <SkeletonBlock class="h-72" />
        <SkeletonBlock class="h-72" />
      </div>
      <SkeletonBlock class="h-32 mt-4" />
    </template>

    <DashboardEmptyState v-else-if="isEmpty" @new-import="$router.push('/runs/new')" />

    <template v-else>
      <BalanceTileGrid :data="summary.data?.balance_tiles" :currency="summary.data?.currency" />

      <div class="grid lg:grid-cols-2 gap-4 mt-4">
        <IncomeExpenseChart
          :income="summary.data?.income_total"
          :expense="summary.data?.expense_total"
          :currency="summary.data?.currency"
          :period="summary.data?.period"
        />
        <CategoryBreakdownCard
          :income-by="summary.data?.income_by_category"
          :expense-by="summary.data?.expense_by_category"
          :currency="summary.data?.currency"
        />
      </div>

      <RecentImportsStrip
        :runs="summary.data?.recent_runs"
        @open="run => $router.push(`/runs/${run.name}`)"
        @new-import="$router.push('/runs/new')"
      />
    </template>
  </div>
</template>
```

`isEmpty` computed per TD-4 predicate above.

### `BalanceTileGrid.vue` + `BalanceTile.vue`

Grid: `grid grid-cols-2 lg:grid-cols-4 gap-3`. Four tiles always
rendered (skeleton when `data` is null). Tile keys: `cash_bank`,
`receivable`, `payable`, `net_for_period`.

`BalanceTile.vue`:

```vue
<template>
  <div class="rounded-lg border border-border bg-surface p-4">
    <div class="flex items-center gap-2 text-sm text-ink-3">
      <component :is="icon" class="w-4 h-4" />
      <span>{{ label }}</span>
    </div>
    <AmountDisplay
      :amount="data?.amount"
      :currency="currency"
      class="block text-2xl font-semibold mt-2"
    />
    <DeltaChip
      v-if="data?.prior_amount != null"
      :current="data.amount"
      :prior="data.prior_amount"
      :favorable-direction="favorableDirection"
      class="mt-1"
    />
  </div>
</template>
```

`favorableDirection` per tile:
- `cash_bank` → `up`
- `receivable` → `up` (higher AR is mixed; debate-worthy — TD calls it favorable v1 since it represents earned-but-uncollected income)
- `payable` → `down` (lower AP is better)
- `net_for_period` → no delta chip

Icons (lucide):
- cash_bank → `wallet`
- receivable → `arrow-down-circle`
- payable → `arrow-up-circle`
- net_for_period → `trending-up` (or `trending-down` if amount < 0)

### `IncomeExpenseChart.vue`

```vue
<template>
  <div class="rounded-lg border border-border bg-surface p-4">
    <header class="flex items-baseline justify-between mb-3">
      <h3 class="text-base font-medium">Income vs Expense</h3>
      <div class="text-xs text-ink-3">
        Income: <AmountDisplay :amount="income" :currency="currency" inline /> ·
        Expense: <AmountDisplay :amount="expense" :currency="currency" inline /> ·
        Net: <AmountDisplay :amount="net" :currency="currency" inline />
      </div>
    </header>
    <DonutChart
      v-if="hasData"
      :data="chartData"
      :options="donutOptions"
      class="h-64"
    />
    <div v-else class="flex items-center justify-center h-64 text-ink-3 text-sm">
      No transactions in this period
    </div>
  </div>
</template>
```

`chartData`:
```js
const chartData = computed(() => ({
  labels: ['Income', 'Expense'],
  datasets: [{
    data: [income, expense],
    backgroundColor: ['var(--cs-success)', 'var(--cs-danger)'],
    borderWidth: 0,
  }],
}))
```

`donutOptions` includes a center-text plugin showing `Net: X`.

`hasData = (income > 0 || expense > 0)`.

**Chart library import** — try frappe-ui first:

```js
import { DonutChart } from 'frappe-ui'   // verify exists
```

If `DonutChart` not exported by frappe-ui v0.1.x at install time, switch
to `chart.js` + `vue-chartjs`:

```bash
yarn add chart.js vue-chartjs
```

Dev confirms at first run; spec leaves both paths viable.

### `CategoryBreakdownCard.vue` + `CategoryBreakdownList.vue`

Card with two stacked sections on narrow viewports, side-by-side on wide.
Each side renders 5 rows (`category` + `amount` + horizontal mini-bar
proportional to `max(amounts)`). If a side has 0 items, render "No
income in this period." / "No expenses in this period." per design brief.

### `RecentImportsStrip.vue` + `ImportCard.vue`

Horizontal scroll on mobile (`overflow-x-auto snap-x snap-mandatory`),
grid on desktop. Each card has: run name (monospace), StatusPill,
period range, counts summary, modified-relative timestamp. Whole card
is `<router-link to="/runs/{name}">`.

### `DashboardEmptyState.vue`

Centered lucide `bar-chart-3` glyph + title + body + primary
`<Button>+ Start an Import</Button>` (emits `new-import`) + secondary
text link `Change period` that focuses the PeriodSelector
(`document.querySelector('[data-period-selector]')?.focus()` —
PeriodSelector exposes this attribute on its trigger button).

### `PeriodSelector.vue`

Dropdown trigger pill `[ This Month: May 2026 ▼ ]`. Menu items per
TD-2. On select:
- Presets resolve `{ start, end }` via `src/utils/period.js`
  `resolvePresetRange(preset)` — same util used by c005 filter.
- `Custom Range…` opens an in-line date-range picker (frappe-ui's
  `<DateRangePicker>` if available, else two `<Input type="date">`
  in a `<Dialog>`).

Emits `update:period` + `update:preset`. Session state lives on the
parent (`FinanceDashboard`); no internal persistence.

Fiscal year resolver: `frappe.client.get_value('Fiscal Year',
{ year_start_date: ['<=', today], year_end_date: ['>=', today] },
'year_start_date')` — called only when user picks `This Fiscal Year`.
Cached in a module-scope ref for the session.

### `CompanySelector.vue`

```vue
<Autocomplete
  v-model="company"
  reference_doctype="GL Entry"
  reference_fieldname="company"
  placeholder="Company"
/>
```

`reference_doctype="GL Entry"` + `reference_fieldname="company"` so the
selector honors any `set_query` registered on GL Entry's company field
(D5 rule 2). Filter `disabled=0` automatic via Frappe's default Link
query for Company.

### Shared primitives

**`AmountDisplay.vue`:**

```vue
<script setup>
const props = defineProps({
  amount: { type: [Number, null] },
  currency: { type: String, default: 'PKR' },
  inline: { type: Boolean, default: false },
})
const formatted = computed(() => {
  if (props.amount == null) return '—'
  try {
    return new Intl.NumberFormat(navigator.language || 'en-PK', {
      style: 'currency', currency: props.currency,
      maximumFractionDigits: 2,
    }).format(props.amount)
  } catch {
    return `${props.currency} ${props.amount.toLocaleString()}`
  }
})
</script>
<template><span class="tabular-nums" :class="{ 'inline-block': inline }">{{ formatted }}</span></template>
```

**`DeltaChip.vue`:**

```vue
<script setup>
const props = defineProps({
  current: Number, prior: Number,
  favorableDirection: { type: String, default: 'up' },  // 'up' or 'down'
})
const delta = computed(() => props.current - props.prior)
const pct = computed(() => props.prior === 0 ? null : (delta.value / props.prior) * 100)
const favorable = computed(() => {
  if (delta.value === 0) return null
  return (delta.value > 0) === (props.favorableDirection === 'up')
})
</script>
<template>
  <span
    class="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full"
    :class="favorable === null ? 'text-ink-3' : favorable ? 'text-success bg-success-50' : 'text-danger bg-danger-50'"
  >
    <component :is="delta > 0 ? ArrowUp : ArrowDown" class="w-3 h-3" />
    {{ pct != null ? `${pct.toFixed(1)}% vs prior` : `${delta > 0 ? '+' : ''}${delta}` }}
  </span>
</template>
```

CSS vars `--cs-success` / `--cs-danger` defined in `src/index.css`
alongside the accent vars (extend c001's :root block — add
`--cs-success: #16a34a; --cs-success-50: #f0fdf4; --cs-danger: #dc2626;
--cs-danger-50: #fef2f2;`).

---

## Acceptance

- [ ] `/` renders Finance Dashboard. Default period = "This Month".
- [ ] Skeleton state on first fetch.
- [ ] Empty state renders when all of `income_total === 0 && expense_total === 0
      && balance_tiles.*.amount === 0 && recent_runs.length === 0`.
- [ ] Normal state renders when ANY of those non-zero.
- [ ] PeriodSelector with 6 presets; selecting one re-fetches.
- [ ] Custom Range opens a date picker; Apply re-fetches.
- [ ] CompanySelector hidden when user has 1 visible company.
- [ ] CompanySelector visible + functional when user has >1 visible
      company; changing it re-fetches.
- [ ] BalanceTileGrid renders 4 tiles with correct icons. Cash & Bank,
      Receivable, Payable show DeltaChip when `prior_amount` present;
      Net for Period never shows delta.
- [ ] IncomeExpenseChart donut renders + tooltip text correct + center
      Net label correct sign.
- [ ] CategoryBreakdownCard shows up to 5 income + 5 expense rows with
      proportional mini-bars; empty side shows fallback text.
- [ ] RecentImportsStrip shows up to 5 cards; click navigates.
- [ ] Realtime subscription on mount; debounced 2s re-fetch on any
      `Cashew Import Run` `doc_update`.
- [ ] Unsubscribe on `onBeforeUnmount` (no leaked listener).
- [ ] No `localStorage` / `sessionStorage` access — grep the page
      directory; zero hits.
- [ ] Currency formats as `Intl.NumberFormat(navigator.language, ...)`;
      e.g. `PKR 1,52,400.00` on `en-PK` locale.
- [ ] When `summary` errors (e.g. user lacks GL Entry:read), shell toast
      surfaces it (c004 interceptor) AND `BalanceTileGrid` /
      `IncomeExpenseChart` / `CategoryBreakdownCard` render their error
      sub-state with a retry icon button.

---

## Files touched

```
frontend/src/pages/FinanceDashboard.vue                        # REPLACE c004 stub
frontend/src/components/finance-dashboard/PageHeader.vue       # NEW (or use shared)
frontend/src/components/finance-dashboard/PeriodSelector.vue   # NEW (shared)
frontend/src/components/finance-dashboard/CompanySelector.vue  # NEW
frontend/src/components/finance-dashboard/BalanceTileGrid.vue  # NEW
frontend/src/components/finance-dashboard/BalanceTile.vue      # NEW
frontend/src/components/finance-dashboard/IncomeExpenseChart.vue # NEW
frontend/src/components/finance-dashboard/CategoryBreakdownCard.vue # NEW
frontend/src/components/finance-dashboard/CategoryBreakdownList.vue # NEW
frontend/src/components/finance-dashboard/RecentImportsStrip.vue # NEW
frontend/src/components/finance-dashboard/ImportCard.vue       # NEW
frontend/src/components/finance-dashboard/DashboardEmptyState.vue # NEW
frontend/src/components/shared/AmountDisplay.vue               # NEW
frontend/src/components/shared/DeltaChip.vue                   # NEW
frontend/src/components/shared/PageHeader.vue                  # NEW
frontend/src/components/shared/EmptyState.vue                  # NEW
frontend/src/components/shared/SkeletonBlock.vue               # NEW
frontend/src/components/shared/StatusPill.vue                  # NEW (also c005)
frontend/src/utils/period.js                                   # NEW — resolvePresetRange + resolvePeriodRange
frontend/src/index.css                                         # EXTEND — add --cs-success / --cs-danger CSS vars
```

If `chart.js` route picked: also
```
frontend/package.json                          # add chart.js + vue-chartjs (Dev verifies frappe-ui first)
```

---

## TD calls inside arch envelope (not surfacing)

- **Chart library = frappe-ui wrapper first, chart.js fallback.** Avoids
  another dependency if frappe-ui already exports DonutChart. Dev checks
  during c001 build.
- **Receivable favorable direction = up.** Debatable; AR going up means
  more uncollected income, which is mixed. Pick up = favorable v1
  because the operator's mental model is "more money I'm owed = better
  business". Document inside the component; revisit if accountants
  complain.
- **Currency from `dashboard_summary.currency` (per-call)**, not boot.
  Allows the CompanySelector to switch currency without a full reload.
- **`Intl.NumberFormat` with `navigator.language` fallback to `en-PK`.**
  Avoids dragging in a locale dep; covers ~95% of cases. Future-proof:
  Cashew Settings could carry a locale field; not v1.
- **Empty-state predicate is strict.** Returning to the empty state from
  a "no recent runs but old balances" case would be wrong (the user
  HAS balances — show them). The conjunction is correct.
- **Period state lives on the page, not in `useDashboardPeriod` (c004
  stub).** c004 stub exists for cross-page sharing if needed; v1 each
  page owns its own period state since the brief never asks for
  "remember period across pages". If that changes, hoist into the c004
  composable.

---

## Open items (handed off)

- **frappe-ui DonutChart availability** — Dev confirms at install. If
  missing, `yarn add chart.js vue-chartjs` and update IncomeExpenseChart
  imports.
- **`@vueuse/core` for `useDebounceFn`** — frappe-ui already pulls
  `@vueuse/core` transitively (verify in `yarn.lock`); else ship a
  3-line inline `function debounce(fn, ms) { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms) } }`.
- **PeriodSelector custom range UX** — picker library choice deferred
  to Dev; native HTML5 date-range fallback ships if frappe-ui has none.
- **Realtime debounce of 2s** — matches the design brief. If users see
  flicker during heavy posting bursts, raise to 5s.
- **CSV-export of dashboard** — out of scope; future feature.
- **Tile click → ledger drill-through** — out of scope.
