# c006 — run-workspace-page (main shard)

> **Type:** ui-page (largest in f010)
> **Depends on:** c004 (router + shell + composables), c008 (per-run realtime
> subscription, expected but page works without)
> **Arch refs:** D5 (hybrid API), D6 (session-only state), D7/D11 (workspace
> owns row UX natively), D8 (per-run realtime), D10 (state-driven sections,
> `router.replace` after parse)
> **Design brief:** `.fb/ui/pages/run-workspace.md` (~500 lines — source of
> truth for visual shape, columns, copy, breakpoints)
> **React reference:** `design_handoff_f010_cashew_spa/design-reference/src/Workspace.jsx`
> **Companion spec:** `c006-spec-b.md` (Section III RowsWorkbench detail —
> the D11 heart)

---

## Shard layout

c006 is large; split for readability:

- **`c006-spec.md` (this file):** page root, route resolution, RunHeader,
  StateStepper, UploadSection (I), PreviewSection (II), CompletedSummary
  (IV), realtime hookup, file tree, acceptance for the shell.
- **`c006-spec-b.md`:** Section III RowsWorkbench in full — toolbar, filter
  facets + chips, RowsTable column registry, SelectionFooter, InlineRowDrawer,
  ValidationFixModal, BulkPartyModal, InlinePartyEdit, column / filter /
  action declarative registries (D11), workbench acceptance.

Both ship together. The Dev work is one PR.

---

## Overview

One page component (`RunWorkspace.vue`) that resolves at both `/runs/new`
and `/runs/:run_name`. State-driven section dispatch from `run.status`:

| `run.status` | Section component |
|---|---|
| `Draft` (or `/runs/new` w/ no record) | `UploadSection` |
| `Parsed` | `PreviewSection` |
| `Validated` / `Queued` / `Processing` | `RowsWorkbench` (see b.md) |
| `Completed` / `Failed` / `Cancelled` / `Reverting` / `Reverted` / `Revert-Failed` | `CompletedSummary` |

`RunHeader` (Section A) + optional `StateStepper` (Section B) are constant
across all states.

---

## Routes (in c004; restated)

```js
{ path: '/runs/new',        name: 'run-new',  component: RunWorkspace },
{ path: '/runs/:run_name',  name: 'run-view', component: RunWorkspace, props: true },
```

Same component, distinguished by `useRoute().params.run_name`:

- `/runs/new` → `run_name = undefined`; UploadSection renders even before
  a record exists (D10).
- `/runs/:run_name` → fetch run, dispatch section by status.

On parse success from UploadSection → `router.replace('/runs/' + new_name)`
(NOT push) — back-button must not land on stale `/runs/new` state per
D10.b.

---

## File tree

```
frontend/src/pages/
  RunWorkspace.vue                          # replaces c004 stub

frontend/src/components/run-workspace/
  RunHeader.vue                             # A — sticky chrome
  StateStepper.vue                          # B
  sections/
    UploadSection.vue                       # I
    PreviewSection.vue                      # II
    RowsWorkbench.vue                       # III (see c006-spec-b.md)
    CompletedSummary.vue                    # IV
  upload/
    CompanyPicker.vue
    CsvDropzone.vue
    OptionalConfigDisclosure.vue
  preview/
    ParseStatsBar.vue
    PreviewTable.vue                        # read-only variant of RowsTable
  completed/
    ResultBanner.vue
    CountsGrid.vue
    PostedBreakdown.vue
    DangerZone.vue
  workbench/                                # populated by c006-spec-b.md
    # ...

frontend/src/composables/
  useRun.js                                 # fetch + reactive run doc
  useRunRealtime.js                         # subscribeDoc + per-row patcher
```

---

## Top-level data: `useRun(run_name)`

```js
// frontend/src/composables/useRun.js
import { createResource } from 'frappe-ui'
import { ref, watch } from 'vue'

export function useRun(runName) {
  const doc = ref(null)
  const rows = ref([])
  const loading = ref(true)
  const error = ref(null)

  const resource = createResource({
    url: 'frappe.client.get_doc',
    cache: false,
    makeParams: () => ({
      doctype: 'Cashew Import Run',
      name: runName.value,
    }),
    onSuccess: (data) => {
      doc.value = data
      rows.value = data.import_rows || []
      loading.value = false
    },
    onError: (e) => { error.value = e; loading.value = false },
  })

  watch(runName, (n) => {
    if (n) resource.reload()
    else { doc.value = null; rows.value = []; loading.value = false }
  }, { immediate: true })

  function patchDoc(partial) {
    if (!doc.value) return
    Object.assign(doc.value, partial)
  }

  function patchRow(row_idx, partial) {
    const i = rows.value.findIndex(r => r.row_idx === row_idx)
    if (i >= 0) rows.value[i] = { ...rows.value[i], ...partial }
  }

  function replaceAllRows(newRows) { rows.value = newRows }

  return { doc, rows, loading, error, reload: resource.reload, patchDoc, patchRow, replaceAllRows }
}
```

`get_doc` returns the run + its `import_rows` child table in one call.
The brief's "TD-time pick" between using this child-table fetch vs
`row_explorer_load` resolves here: **default to `get_doc.import_rows`**.
Switch to `row_explorer_load` only if (a) row counts exceed ~5k per
run and the get_doc payload becomes slow, or (b) we need a projection
that get_doc doesn't carry. Today's runs (~hundreds of rows) are fine.

---

## `RunWorkspace.vue` — page root

```vue
<script setup>
import { useRoute, useRouter } from 'vue-router'
import { computed, watch } from 'vue'
import { useRun } from '@/composables/useRun'
import { useRunRealtime } from '@/composables/useRunRealtime'
import RunHeader from '@/components/run-workspace/RunHeader.vue'
import StateStepper from '@/components/run-workspace/StateStepper.vue'
import UploadSection from '@/components/run-workspace/sections/UploadSection.vue'
import PreviewSection from '@/components/run-workspace/sections/PreviewSection.vue'
import RowsWorkbench from '@/components/run-workspace/sections/RowsWorkbench.vue'
import CompletedSummary from '@/components/run-workspace/sections/CompletedSummary.vue'
import { SkeletonBlock } from '@/components/shared'

const route = useRoute()
const router = useRouter()
const runName = computed(() => route.params.run_name || null)
const { doc, rows, loading, error, reload, patchDoc, patchRow } = useRun(runName)

useRunRealtime(runName, { patchDoc, patchRow })

const status = computed(() => doc.value?.status || (runName.value ? null : 'Draft'))

const sectionComponent = computed(() => {
  if (!runName.value || status.value === 'Draft') return UploadSection
  if (status.value === 'Parsed') return PreviewSection
  if (['Validated', 'Queued', 'Processing'].includes(status.value)) return RowsWorkbench
  if (['Completed', 'Failed', 'Cancelled', 'Reverting', 'Reverted', 'Revert-Failed'].includes(status.value)) return CompletedSummary
  return null
})

function onParsed(newRunName) {
  router.replace(`/runs/${newRunName}`)
}
</script>

<template>
  <div class="flex flex-col h-full">
    <RunHeader
      :doc="doc"
      :run-name="runName"
      :loading="loading"
      @reload="reload"
    />
    <StateStepper :status="status" />

    <div class="flex-1 overflow-y-auto px-4 py-4 max-w-7xl mx-auto w-full">
      <SkeletonBlock v-if="loading && !doc" class="h-96" />
      <ErrorCard v-else-if="error" :error="error" @retry="reload" />
      <component
        v-else
        :is="sectionComponent"
        :doc="doc"
        :rows="rows"
        :run-name="runName"
        @reload="reload"
        @parsed="onParsed"
        @patch-doc="patchDoc"
        @patch-row="patchRow"
      />
    </div>
  </div>
</template>
```

---

## Realtime: `useRunRealtime(runName, { patchDoc, patchRow })`

```js
// frontend/src/composables/useRunRealtime.js
import { watch, onBeforeUnmount } from 'vue'
import { subscribeDoc } from '@/realtime'  // c008

export function useRunRealtime(runName, { patchDoc, patchRow }) {
  let unsub

  watch(runName, (n) => {
    unsub?.()
    if (!n) return
    unsub = subscribeDoc('Cashew Import Run', n, (event) => {
      // event.doc carries the changed run; event.rows (optional) carries
      // changed rows by row_idx. c008 normalizes the payload shape.
      if (event.doc) patchDoc(event.doc)
      if (event.rows) event.rows.forEach(r => patchRow(r.row_idx, r))
    })
  }, { immediate: true })

  onBeforeUnmount(() => unsub?.())
}
```

Until c008 ships, `subscribeDoc` returns a no-op unsubscribe; page works
without live updates — manual action callbacks call `reload()`.

---

## `RunHeader.vue` (Section A)

Two rows. Sticky at top. Background = surface; border-bottom = border.

**Row 1 — identity:**
- `<` back chevron → `/runs`
- Run name (monospace; `(new import)` when `runName == null`)
- `<StatusPill :status="doc.status" />`
- Realtime "● Live" indicator when `useRealtimeStatus().value === 'connected'`
  (consumes c004 composable)
- "Open in Desk" small icon link → new tab `/app/cashew-import-run/{name}`

**Row 2 — metadata + actions:**

Left facts string:
```
{company} · {periodFmt} · {rows_total} rows · {rows_valid} valid · {rows_failed} failed · {rows_posted} posted
```
Hide segments where the count is 0 / null. `periodFmt` is
`formatRange(doc.period_start, doc.period_end)` from `src/utils/period.js`;
falls back to `—` if either is null.

Right action buttons via `<ActionButton>` (a thin wrapper that handles
loading + disabled + confirm). Buttons resolved from a **status → action
map** declared once at the top of RunHeader.vue (D11 — declarative
action registry):

```js
const RUN_ACTIONS = {
  Draft: [
    { id: 'parse', label: 'Parse', primary: true, disabledIf: d => !d.source_file, method: 'parse_and_preview' },
    { id: 'discard', label: 'Delete draft', danger: true, confirmText: 'Delete this draft?', deleteDoc: true },
  ],
  Parsed: [
    { id: 'validate', label: 'Validate', primary: true, method: 'validate_import' },
    { id: 'reparse', label: 'Re-parse', method: 'parse_and_preview' },
    { id: 'discard', label: 'Discard', danger: true, confirmText: 'Discard this run? Posted documents will NOT be touched.', deleteDoc: true },
  ],
  Validated: [
    { id: 'queue', label: 'Queue Import', primary: true, method: 'queue_run',
      confirmText: d => `Post ${d.rows_valid} valid rows to the GL?` },
    { id: 'revalidate', label: 'Re-validate', method: 'validate_import' },
    { id: 'discard', label: 'Discard', danger: true, confirmText: 'Discard this run?', deleteDoc: true },
  ],
  Queued:     [{ id: 'cancel', label: 'Cancel', danger: true, method: 'cancel_run', confirmText: 'Cancel this queued import?' }],
  Processing: [{ id: 'cancel', label: 'Cancel', danger: true, method: 'cancel_run', confirmText: 'Cancel this processing import?' }],
  Completed: [
    { id: 'revert', label: 'Revert', danger: true, method: 'revert_run',
      confirmText: 'This will reverse every posted document. Continue?' },
    { id: 'diag', label: 'Download diagnostics CSV', linkField: 'diagnostics_file' },
  ],
  Failed: [
    { id: 'revalidate', label: 'Re-validate', primary: true, method: 'validate_import' },
    { id: 'diag', label: 'Download diagnostics CSV', linkField: 'diagnostics_file' },
    { id: 'discard', label: 'Discard', danger: true, confirmText: 'Discard this run?', deleteDoc: true },
  ],
  Cancelled: [
    { id: 'requeue', label: 'Re-queue', primary: true, method: 'queue_run',
      confirmText: 'Re-queue this import?' },
    { id: 'discard', label: 'Discard', danger: true, deleteDoc: true },
  ],
  Reverting: [],
  Reverted: [
    { id: 'requeue', label: 'Re-queue', method: 'queue_run' },
    { id: 'discard', label: 'Discard', deleteDoc: true },
  ],
  'Revert-Failed': [
    { id: 'retry-revert', label: 'Retry Revert', danger: true, method: 'revert_run',
      confirmText: 'Retry revert?' },
  ],
}
```

`ActionButton` consumes one entry; on click:
- `method` set → opens `<ConfirmDialog>` if `confirmText` defined; on
  confirm → `frappe.call('cashew_integration.api.' + method, { run_name })`.
  On success → emit `reload` (parent re-fetches run). On error →
  c004's interceptor toasts; button re-enables.
- `linkField` set → `window.open(doc[linkField], '_blank')`.
- `deleteDoc: true` → confirm → `frappe.client.delete('Cashew Import Run', name)` →
  `router.replace('/runs')`.

This registry is the D11 declarative action surface. New actions plug
in here without touching component code.

---

## `StateStepper.vue` (Section B)

4-step bar. Static mapping per design brief:

```js
const STEPS = [
  { id: 'upload',    label: 'Upload',    statuses: ['Draft'] },
  { id: 'preview',   label: 'Preview',   statuses: ['Parsed'] },
  { id: 'workbench', label: 'Workbench', statuses: ['Validated', 'Queued', 'Processing'] },
  { id: 'done',      label: 'Done',      statuses: ['Completed', 'Failed', 'Cancelled', 'Reverting', 'Reverted', 'Revert-Failed'] },
]
```

Active step: matched on `status`. Steps before active = completed
(muted-green check). Steps after active = grey. Mobile (`<sm`) collapses
to single label `Step 3 of 4: Workbench`.

Not clickable. Pure indicator.

---

## Section I — `UploadSection.vue` (status = Draft or runName == null)

```vue
<template>
  <div class="max-w-2xl mx-auto py-8 space-y-6">
    <CompanyPicker
      v-if="!runName"
      v-model="state.company"
    />
    <CsvDropzone
      v-model:file-url="state.source_file"
      v-model:filename="state.source_filename"
    />
    <OptionalConfigDisclosure
      v-model:balance-adjustment-account="state.balance_adjustment_account"
      v-model:je-rounding-tolerance="state.je_rounding_tolerance"
    />
    <div class="flex gap-2 justify-end">
      <RouterLink to="/runs" class="text-ink-3 underline">Cancel</RouterLink>
      <Button
        variant="solid"
        theme="accent"
        :disabled="!canParse"
        :loading="state.parsing"
        @click="onParse"
      >
        Parse →
      </Button>
    </div>
  </div>
</template>
```

`onParse` (binding logic):
1. If `runName == null`: `frappe.call('frappe.client.insert', { doc: {
   doctype: 'Cashew Import Run',
   company: state.company,
   source_file: state.source_file,
   balance_adjustment_account: state.balance_adjustment_account || null,
   je_rounding_tolerance: state.je_rounding_tolerance || 0.01,
   } })` → get back `newDoc.name`.
   Otherwise use `runName.value`.
2. `frappe.call('cashew_integration.api.parse_and_preview', { run_name: newName })`.
3. On success: emit `parsed` with `newName`. Page root calls
   `router.replace('/runs/' + newName)`.
4. On error: shell toast already fired by interceptor; re-enable button.

Note: there is currently no `setup_from_csv`-style direct-CSV-upload helper
for creating a Run + parsing in one step. The flow above is two API calls,
matching the existing Desk form behavior.

### `CompanyPicker.vue`

```vue
<Autocomplete
  v-model="company"
  reference_doctype="Cashew Import Run"
  reference_fieldname="company"
  placeholder="Company"
/>
```

Default value: `useCashewSettings().value.default_company ||
useSysDefaults().value.default_company`.

### `CsvDropzone.vue`

Drag-and-drop + click-to-browse. Frappe's file upload pattern:

```js
async function uploadFile(file) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('is_private', '1')
  fd.append('folder', 'Home/Cashew Imports')   // optional grouping
  const res = await fetch('/api/method/upload_file', {
    method: 'POST',
    headers: { 'X-Frappe-CSRF-Token': window.boot.csrf_token },
    body: fd,
  })
  const json = await res.json()
  return json.message.file_url   // e.g. "/private/files/abc.csv"
}
```

Accept `.csv` (mime `text/csv,application/vnd.ms-excel`). Show filename +
size + remove (✗) button when picked. Validate `< 50 MB` client-side
before upload (Frappe's `max_file_size` is configurable; 50 MB is a
generous floor for Cashew exports).

### `OptionalConfigDisclosure.vue`

Collapsible card. Two fields:
- `balance_adjustment_account` — `<Autocomplete reference_doctype="Cashew Import Run"
   reference_fieldname="balance_adjustment_account">`. Default empty.
- `je_rounding_tolerance` — `<Input type="number" step="0.01" />`. Default `0.01`.

Hidden by default; click "Advanced ▾" to expand.

---

## Section II — `PreviewSection.vue` (status = Parsed)

```vue
<template>
  <div class="space-y-4">
    <ParseStatsBar :doc="doc" :rows="rows" />
    <PreviewTable :rows="rows" />
    <div class="flex gap-2 justify-end">
      <Button variant="ghost" @click="onReparse" :loading="state.reparsing">Re-parse</Button>
      <Button variant="ghost" :danger="true" @click="onDiscard">Discard</Button>
      <Button variant="solid" theme="accent" @click="onValidate" :loading="state.validating">Validate →</Button>
    </div>
  </div>
</template>
```

`onValidate` → `frappe.call('cashew_integration.api.validate_import', { run_name: runName })`.
On success → server pushes new `status = Validated` via doc_update; section
swap follows. (Belt-and-braces: emit `reload` after the call.)

### `ParseStatsBar.vue`

Horizontal flex-wrap row of `<StatCell>` tiles. Computed counts derived
from `rows`:

```js
const counts = computed(() => {
  const c = { income: 0, expense: 0, transfer: 0, loan: 0, adjust: 0, dup: 0 }
  for (const r of props.rows) {
    if (r.txn_type === 'Income') c.income++
    else if (r.txn_type === 'Expense') c.expense++
    else if (['Transfer', 'External Transfer'].includes(r.txn_type)) c.transfer++
    else if (['Loan Receivable', 'Loan Payable'].includes(r.txn_type)) c.loan++
    else if (r.txn_type === 'Adjustment') c.adjust++
    if (r.is_duplicate) c.dup++
  }
  return c
})
```

Tiles in order: Total rows · Period · Income · Expense · Transfers ·
Loans · Adjustments · Duplicates. Hide a tile if its count is 0 (except
Total + Period which always show).

### `PreviewTable.vue`

Read-only variant of `RowsTable` (defined in c006-spec-b.md). v1: just
import the workbench RowsTable in "preview mode" — no select column, no
inline edit, no kebab. Columns visible: `#`, Date, Account, Amount,
Type, Category (+ sub-category beneath), Note (truncated).

Pagination (25/page, same `Pagination.vue` as c005). No filters.

---

## Section IV — `CompletedSummary.vue` (terminal states)

```vue
<template>
  <div class="space-y-4">
    <ResultBanner :doc="doc" />
    <CountsGrid :doc="doc" />
    <PostedBreakdown :rows="rows" :doc="doc" />

    <details class="rounded-lg border border-border p-3">
      <summary class="cursor-pointer text-sm font-medium">Row results</summary>
      <RowsTable
        :doc="doc"
        :rows="rows"
        read-only
        :default-filter="defaultPostFilter"
        :default-preset="'Posting-focused'"
      />
    </details>

    <DangerZone :doc="doc" @reload="$emit('reload')" />
  </div>
</template>
```

`defaultPostFilter`: filter to Posted = Failed/Reverted when the run has
any failed rows; else "Show all".

### `ResultBanner.vue`

Color by status:
- green: `Completed`
- amber: `Cancelled`, `Reverted`, `Reverting`
- red: `Failed`, `Revert-Failed`

Title: `✓ Completed — N rows posted (M failed)` / `⨯ Failed — see diagnostics`
/ `↺ Reverted — N posted documents reversed` / etc.

Subtitle: `Started {relative} · Finished {relative}` from
`doc.started_on` + `doc.finished_on`. Hidden if either null.

### `CountsGrid.vue`

`<StatCell>` tiles: Total, Valid, Posted, Failed, Skipped. Each value
from `doc.rows_*`. AmountDisplay style: tabular-nums, right-aligned in
each tile.

### `PostedBreakdown.vue`

Horizontal bar chart or list — TD picks **list** for v1 (simpler, no
chart-lib cost):

```vue
<ul class="space-y-2">
  <li v-for="b in breakdown" :key="b.label" class="flex items-center justify-between text-sm">
    <span>{{ b.label }}</span>
    <span class="tabular-nums">{{ b.count }}</span>
  </li>
</ul>
```

Computed:
```js
const breakdown = computed(() => {
  const counts = new Map()
  for (const r of props.rows) {
    if (!r.posted_doctype) continue
    counts.set(r.posted_doctype, (counts.get(r.posted_doctype) || 0) + 1)
  }
  return [...counts.entries()].map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count)
})
```

Donut chart deferred — list is enough for v1.

### `DangerZone.vue`

Subdued red-accent card. Content varies by status:

- `Completed` → `Revert this import` headline + Revert button (danger,
  confirm) + Download diagnostics link
- `Failed` → Re-validate / Re-queue buttons + diagnostics link
- `Cancelled` → Re-queue button
- `Reverting` → progress bar (`<Progress :value="postedPct" />`) only
- `Reverted` → Re-queue or Discard
- `Revert-Failed` → Retry Revert + Open in Desk link

All buttons consume the same `RUN_ACTIONS` registry from RunHeader
(re-imported). Single source of truth for the action set.

---

## Realtime contract (per D8)

Subscribe to `Cashew Import Run` `doc_update` scoped to current run
(`useRunRealtime`). Fields the page consumes from realtime:

| Field | Effect |
|---|---|
| `status` | Triggers section swap (via `patchDoc`) |
| `rows_total`, `rows_valid`, `rows_failed`, `rows_posted`, `rows_skipped` | Header counts update |
| `import_rows[].validation_status` | Row pills update |
| `import_rows[].posted_doctype` / `posted_docname` | Row "Posted" badge / link |
| `import_rows[].revert_status` / `revert_error` | Revert column |

Fallback: on permanent socket loss, c008 polls
`cashew_integration.api.get_run_progress(run_name)` every 30s and
publishes synthetic doc_update events. Page consumes them identically.

---

## Acceptance (shell + I/II/IV; III in c006-spec-b.md)

- [ ] `/runs/new` renders UploadSection without a record.
- [ ] CompanyPicker default = Cashew Settings.default_company → boot
      sysdefault → null. Hidden once record exists.
- [ ] CsvDropzone drag + click upload works; file size > 50 MB rejected
      client-side; private upload (`is_private=1`).
- [ ] OptionalConfigDisclosure collapsed by default; fields persist
      onto run record on Parse.
- [ ] Parse on `/runs/new`: creates record + calls parse_and_preview +
      `router.replace('/runs/' + name)`.
- [ ] Parse on `/runs/:name` (Draft status): calls parse_and_preview;
      status transitions to Parsed; PreviewSection auto-renders.
- [ ] PreviewSection: ParseStatsBar shows correct counts; tiles with
      count=0 are hidden.
- [ ] PreviewTable is read-only — no select column, no inline edit, no
      kebab.
- [ ] Validate from Preview transitions to Validated → RowsWorkbench
      renders (covered in b.md).
- [ ] CompletedSummary: ResultBanner color matches status; CountsGrid
      shows all 5 counts; PostedBreakdown lists posted-doctype counts;
      collapsible row results table at the bottom.
- [ ] DangerZone shows the right buttons per terminal status.
- [ ] RunHeader actions resolve from RUN_ACTIONS registry; disabled +
      loading states correct; ConfirmDialog blocks destructive actions.
- [ ] Realtime: changing the run's status server-side (e.g. via Desk
      form) updates the page within ~1s without manual refresh.
- [ ] Realtime unsubscribe on route leave / unmount (no leaked listener;
      grep for `subscribeDoc` callers, every one has an `onBeforeUnmount`
      unsubscribe).
- [ ] No `localStorage` / `sessionStorage` access — grep the directory
      tree under `src/pages/RunWorkspace.vue` +
      `src/components/run-workspace/` + `src/composables/useRun.js` +
      `src/composables/useRunRealtime.js`; zero hits.

---

## TD calls inside arch envelope (not surfacing)

- **`get_doc.import_rows` over `row_explorer_load`.** Simpler (one call,
  one cache). Switch to row_explorer_load only if get_doc payload
  becomes slow for large runs.
- **Declarative RUN_ACTIONS registry.** D11 prescribes declarative
  action registries; this is the run-level one. Per-row action registry
  lives in c006-spec-b.md.
- **PostedBreakdown as a list, not a chart.** Avoids dragging chart.js
  into c006 if c007 didn't already. If c007 ships frappe-ui DonutChart,
  PostedBreakdown can swap to donut for free in a future revision.
- **Action button confirmation pattern centralized.** All destructive
  actions route through `<ConfirmDialog>`; `confirmText` is a string OR
  a function of `doc` (Queue Import passes `rows_valid` count in the
  prompt).
- **`router.replace` (not push) after parse on /runs/new.** D10.b
  explicit. Implemented in `onParsed`.
- **No `/runs/new` redirect** when user lands at `/runs/new` and
  immediately sees a Draft run with the same source_file already
  attached — there's no such case; UploadSection always creates a
  fresh record. (If we add "resume draft" UX later, that flow needs
  new spec.)

---

## Open items (handed off to c008 + b.md)

- **`subscribeDoc` payload shape** — c008 to define event shape. Spec
  assumes `{ doc?: partialDoc, rows?: [{ row_idx, ...partialRow }] }`.
- **Polling fallback shape** — c008's get_run_progress emits synthetic
  doc_update; field set should match the live one.
- **PreviewTable as workbench-RowsTable preview mode** — implement in
  b.md. If b.md goes a different direction, swap PreviewTable
  implementation in II then.
- **`StatCell` shared primitive** — used by ParseStatsBar +
  CountsGrid + BalanceTileGrid (c007). Either reuse `BalanceTile.vue`
  (rename to StatCell) or author a separate one. Dev's call at
  implementation; both are 30-line components.
- **Section transition animation** — design brief asks for status pill
  to "animate to new color" + content section auto-switch. v1: simple
  Vue `<Transition mode="out-in">` on the section dispatcher. No
  custom keyframes.
