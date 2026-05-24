# c006 — run-workspace-page (b: RowsWorkbench detail)

> **Companion to:** `c006-spec.md`
> **Covers:** Section III RowsWorkbench — the D11 heart of run-workspace.
> Toolbar, filter facets, declarative chip rendering, RowsTable with
> dynamic column registry, SelectionFooter, ValidationFixModal,
> BulkPartyModal, InlinePartyEdit, InlineRowDrawer. Bulk actions
> registry. Workbench acceptance.

---

## When rendered

`doc.status in ('Validated', 'Queued', 'Processing')`.

Mode shifts:
- **`Validated`** → full edit mode. Inline edits, bulk actions,
  validate.
- **`Queued` / `Processing`** → read-mostly mode. No inline edits, no
  bulk-write actions; rows update live from realtime as the worker
  posts them.

Mode is a computed boolean `editable = doc.status === 'Validated'`.
Every edit action gates on `editable.value`.

---

## File tree

```
frontend/src/components/run-workspace/workbench/
  WorkbenchToolbar.vue
  ActiveFilterChips.vue
  RowsTable.vue                  # the big data grid
  RowsCardList.vue               # <640px card variant
  RowCard.vue                    # one card
  RowKebabMenu.vue
  SelectionFooter.vue
  InlineRowDrawer.vue
  ValidationFixModal.vue
  BulkPartyModal.vue
  InlinePartyEdit.vue
  registries/
    columns.js                   # COLUMN_DEFS + COLUMN_PRESETS
    filters.js                   # FILTER_FACETS
    bulkActions.js               # BULK_ACTIONS
```

---

## Workbench state model

`RowsWorkbench.vue` owns:

```js
const state = reactive({
  search: '',
  filters: {},                   // { [facetId]: value | values[] }
  preset: null,                  // current column preset (auto-picks on mount)
  visibleColumns: [],            // resolved from preset + per-column toggles
  page: { start: 0, length: 50 }, // local pagination over the rows array
  sort: null,                    // { column, dir } | null (default: row_idx asc)
  selected: new Set(),           // row_idx values
  searchExtendsVisible: false,   // track when search matches in a hidden column
})
```

All in-memory; no persistence (D6).

Derived:

```js
const filtered = computed(() => applyFilters(props.rows, state.filters, state.search))
const sorted   = computed(() => applySort(filtered.value, state.sort))
const pageRows = computed(() => sorted.value.slice(state.page.start, state.page.start + state.page.length))
```

---

## D11 declarative registries

### `registries/columns.js`

```js
import { defineColumn } from './_helpers'

export const COLUMN_DEFS = [
  defineColumn('row_idx',     { header: '#',        align: 'right', sticky: 'left', tabular: true, sortable: true }),
  defineColumn('select',      { header: '',         widthPx: 32,    sticky: 'left', renderer: 'select-checkbox' }),
  defineColumn('validation',  { header: 'Status',   field: 'validation_status', renderer: 'status-pill', sortable: true }),
  defineColumn('txn_date',    { header: 'Date',     field: 'txn_date',       renderer: 'date-short', sortable: true }),
  defineColumn('raw_txn_time',{ header: 'Time',     field: 'raw_txn_time',   renderer: 'time-short' }),
  defineColumn('raw_account', { header: 'Account',  field: 'raw_account',    renderer: 'text' }),
  defineColumn('amount',      { header: 'Amount',   field: 'base_amount',    renderer: 'amount-signed',
                                signFromField: 'income_flag', currencyField: 'company_currency', align: 'right', tabular: true, sortable: true }),
  defineColumn('txn_type',    { header: 'Type',     field: 'txn_type',       renderer: 'type-pill', sortable: true }),
  defineColumn('category',    { header: 'Category', field: 'category',       renderer: 'category-with-sub',
                                subField: 'sub_category', sortable: true }),
  defineColumn('note',        { header: 'Note',     field: 'note',           renderer: 'truncated', titleFromField: 'note' }),
  defineColumn('resolved_account',          { header: 'Resolved Account', field: 'resolved_account', renderer: 'link-account' }),
  defineColumn('resolved_external_account', { header: 'External Account', field: 'resolved_external_account', renderer: 'link-account' }),
  defineColumn('requires_party',            { header: 'Party Reqd', field: 'requires_party', renderer: 'check-icon' }),
  defineColumn('party_type',                { header: 'Party Type', field: 'resolved_party_type' }),
  defineColumn('party',                     { header: 'Party',      field: 'resolved_party',
                                              renderer: 'inline-party-edit', editableWhen: r => r.validation_status !== 'Valid' }),
  defineColumn('validation_error_message',  { header: 'Error',      field: 'validation_error_message', renderer: 'error-text' }),
  defineColumn('validation_error_code',     { header: 'Code',       field: 'validation_error_code',    renderer: 'code-badge' }),
  defineColumn('posted_doctype',            { header: 'Posted Type',field: 'posted_doctype' }),
  defineColumn('posted_docname',            { header: 'Posted Doc', field: 'posted_docname', renderer: 'desk-link',
                                              targetDoctypeField: 'posted_doctype' }),
  defineColumn('posted_gl_date',            { header: 'Posted GL',  field: 'posted_gl_date', renderer: 'date-short' }),
  defineColumn('is_duplicate',              { header: 'Dup',        field: 'is_duplicate',   renderer: 'check-icon' }),
  defineColumn('revert',                    { header: 'Revert',     field: 'revert_status',  renderer: 'revert-pill',
                                              errorField: 'revert_error' }),
  defineColumn('kebab',                     { header: '',           widthPx: 32, sticky: 'right', renderer: 'row-kebab' }),
]

export const COLUMN_PRESETS = {
  'Compact':            ['row_idx', 'select', 'validation', 'txn_date', 'raw_account', 'amount', 'txn_type', 'category', 'kebab'],
  'Validation-focused': ['row_idx', 'select', 'validation', 'txn_date', 'raw_account', 'amount', 'validation_error_message', 'party', 'kebab'],
  'Posting-focused':    ['row_idx', 'select', 'validation', 'txn_date', 'raw_account', 'amount', 'txn_type', 'resolved_account', 'party', 'kebab'],
  'Wide':               COLUMN_DEFS.map(c => c.id),
}

export function pickDefaultPreset(rows, status) {
  const hasErrors = rows.some(r => r.validation_status === 'Error')
  if (hasErrors) return 'Validation-focused'
  if (status === 'Validated') return 'Posting-focused'
  return 'Compact'
}
```

`renderer` strings map to small render functions in
`RowsTable.vue` — switch-on-renderer pattern. New renderers added by
extending the switch; no per-column SFCs needed.

### `registries/filters.js`

```js
export const FILTER_FACETS = [
  {
    id: 'validation_status',
    label: 'Validation Status',
    type: 'select',
    options: ['Valid', 'Error', 'Skipped'],
    apply: (row, value) => !value?.length || value.includes(row.validation_status),
    chipLabel: (value) => `Status: ${Array.isArray(value) ? value.join(', ') : value}`,
  },
  {
    id: 'txn_type',
    label: 'Transaction Type',
    type: 'select',
    options: ['Income', 'Expense', 'Transfer', 'External Transfer', 'Adjustment', 'Loan Receivable', 'Loan Payable'],
    apply: (row, value) => !value?.length || value.includes(row.txn_type),
    chipLabel: (value) => `Type: ${Array.isArray(value) ? value.join(', ') : value}`,
  },
  {
    id: 'category_type',
    label: 'Category Type',
    type: 'select',
    options: ['Income', 'Expense', 'Loan Out', 'Loan In'],
    // derived facet — requires a category-type lookup; see helpers below
    apply: (row, value, ctx) => !value?.length || value.includes(ctx.categoryType(row.category)),
    chipLabel: (value) => `Cat Type: ${Array.isArray(value) ? value.join(', ') : value}`,
  },
  {
    id: 'category',
    label: 'Category',
    type: 'string-facet',
    optionsFrom: 'rows.category',
    apply: (row, value) => !value?.length || value.includes(row.category),
    chipLabel: (value) => `Category: ${Array.isArray(value) ? value.join(', ') : value}`,
  },
  {
    id: 'raw_account',
    label: 'Raw Account',
    type: 'string-facet',
    optionsFrom: 'rows.raw_account',
    apply: (row, value) => !value?.length || value.includes(row.raw_account),
    chipLabel: (value) => `Account: ${Array.isArray(value) ? value.join(', ') : value}`,
  },
  {
    id: 'posted',
    label: 'Posted',
    type: 'tri-state',
    options: ['Posted', 'Not posted', 'Failed'],
    apply: (row, value) => {
      if (!value) return true
      const posted = !!row.posted_docname
      const failed = row.revert_status === 'Revert-Failed' || row.validation_status === 'Error'
      if (value === 'Posted') return posted && !failed
      if (value === 'Not posted') return !posted && !failed
      if (value === 'Failed') return failed
      return true
    },
    chipLabel: (value) => `Posted: ${value}`,
  },
  {
    id: 'has_party',
    label: 'Has party',
    type: 'tri-state',
    options: ['Has party', 'Missing party', 'N/A'],
    apply: (row, value) => {
      if (!value) return true
      if (value === 'Has party') return !!row.resolved_party
      if (value === 'Missing party') return row.requires_party && !row.resolved_party
      if (value === 'N/A') return !row.requires_party
      return true
    },
    chipLabel: (value) => value,
  },
  {
    id: 'is_duplicate',
    label: 'Duplicate',
    type: 'toggle',
    options: ['Yes', 'No', 'Any'],
    apply: (row, value) => value === 'Any' || value == null
      ? true
      : value === 'Yes' ? !!row.is_duplicate : !row.is_duplicate,
    chipLabel: () => 'Duplicates only',
  },
]
```

Facets are pure functions. Adding a facet = adding one entry. New
facets render automatically in the FiltersDropdown and as chips in
ActiveFilterChips.

Category-type lookup helper: `useCategoryTypeMap(runName)` —
issues one `frappe.client.get_list('Cashew Category Mapping', {
fields: ['cashew_category', 'category_type'], limit: 0 })` at mount
and exposes `categoryType(cashewCategory) -> string`. Cached for the
session.

### `registries/bulkActions.js`

```js
export const BULK_ACTIONS = [
  {
    id: 'set_party',
    label: 'Set party…',
    icon: 'user-plus',
    enabledWhen: ({ selectedRows, editable }) => editable && selectedRows.length > 0,
    openModal: 'BulkPartyModal',
  },
  {
    id: 'revalidate_selected',
    label: 'Re-validate selected',
    icon: 'rotate-cw',
    enabledWhen: ({ selectedRows, editable }) => editable && selectedRows.length > 0,
    method: 'row_explorer_revalidate',
    extractParams: ({ runName, selectedRows }) => ({
      run_name: runName,
      row_indices: selectedRows.map(r => r.row_idx),
    }),
    toast: ({ selectedRows }) => `Re-validated ${selectedRows.length} rows`,
  },
  // future actions plug in here — Set category, Mark duplicate, etc.
]
```

---

## `RowsWorkbench.vue` — structure

```vue
<template>
  <div class="space-y-2">
    <WorkbenchToolbar
      v-model:search="state.search"
      :filter-defs="FILTER_FACETS"
      :filter-values="state.filters"
      :column-defs="COLUMN_DEFS"
      :column-presets="COLUMN_PRESETS"
      :preset="state.preset"
      :visible-columns="state.visibleColumns"
      :bulk-actions="BULK_ACTIONS"
      :selected-count="state.selected.size"
      :editable="editable"
      @update:filters="v => state.filters = v"
      @update:preset="onPresetChange"
      @update:visibleColumns="v => state.visibleColumns = v"
      @validate="onValidate"
      @bulk="onBulkAction"
    />

    <ActiveFilterChips
      :filter-defs="FILTER_FACETS"
      :filter-values="state.filters"
      @remove="onRemoveFilter"
      @clear="state.filters = {}"
    />

    <component
      :is="isMobile ? RowsCardList : RowsTable"
      :doc="doc"
      :rows="pageRows"
      :total-filtered="filtered.length"
      :column-defs="COLUMN_DEFS"
      :visible-columns="state.visibleColumns"
      :sort="state.sort"
      :selected="state.selected"
      :editable="editable"
      @select-toggle="onSelectToggle"
      @select-all="onSelectAll"
      @sort="v => state.sort = v"
      @row-click="onRowClick"
      @inline-edit="onInlineEdit"
      @row-action="onRowAction"
    />

    <Pagination
      v-if="filtered.length > state.page.length"
      :start="state.page.start"
      :length="state.page.length"
      :total="filtered.length"
      @page="v => state.page.start = v"
    />

    <SelectionFooter
      v-if="state.selected.size > 0"
      :count="state.selected.size"
      :actions="BULK_ACTIONS.filter(a => a.enabledWhen({ selectedRows, editable }))"
      @action="onBulkAction"
      @clear="state.selected.clear()"
    />

    <InlineRowDrawer
      v-if="drawerRow"
      :row="drawerRow"
      :editable="editable"
      @close="drawerRow = null"
    />

    <ValidationFixModal
      v-if="fixRow"
      :run-name="runName"
      :row="fixRow"
      @close="fixRow = null"
      @saved="onRowSaved"
    />

    <BulkPartyModal
      v-if="bulkPartyOpen"
      :count="state.selected.size"
      :run-name="runName"
      :row-indices="[...state.selected]"
      @close="bulkPartyOpen = false"
      @saved="onBulkSaved"
    />
  </div>
</template>
```

Event handlers:

```js
function onPresetChange(preset) {
  state.preset = preset
  state.visibleColumns = COLUMN_PRESETS[preset]
}

function onSelectToggle(row_idx) {
  if (state.selected.has(row_idx)) state.selected.delete(row_idx)
  else state.selected.add(row_idx)
}
function onSelectAll(allChecked) {
  if (allChecked) state.selected = new Set(filtered.value.map(r => r.row_idx))
  else state.selected = new Set()
}

function onRemoveFilter(facetId, value) {
  const cur = state.filters[facetId]
  if (Array.isArray(cur)) {
    state.filters = { ...state.filters, [facetId]: cur.filter(v => v !== value) }
  } else {
    const { [facetId]: _, ...rest } = state.filters
    state.filters = rest
  }
}

async function onValidate() {
  await frappe.call('cashew_integration.api.validate_import', { run_name: runName.value })
  emit('reload')
}

async function onBulkAction(action) {
  if (action.openModal === 'BulkPartyModal') { bulkPartyOpen.value = true; return }
  if (action.method) {
    const params = action.extractParams({ runName: runName.value, selectedRows: selectedRows.value })
    await frappe.call('cashew_integration.api.' + action.method, params)
    toast(action.toast({ selectedRows: selectedRows.value }))
    state.selected.clear()
    emit('reload')
  }
}

function onInlineEdit({ row_idx, party_type, party }) {
  return frappe.call('cashew_integration.api.row_explorer_set_party', {
    run_name: runName.value,
    row_indices: [row_idx],
    party_type, party,
  })
}

function onRowAction({ action, row }) {
  if (action === 'fix') fixRow.value = row
  else if (action === 'revalidate') frappe.call('cashew_integration.api.row_explorer_revalidate', {
    run_name: runName.value, row_indices: [row.row_idx],
  }).then(() => emit('reload'))
  else if (action === 'view-json') drawerRow.value = row
  else if (action === 'open-posted' && row.posted_docname) {
    const slug = row.posted_doctype.toLowerCase().replace(/ /g, '-')
    window.open(`/app/${slug}/${row.posted_docname}`, '_blank')
  }
}

function onRowClick(row) { drawerRow.value = row }
function onRowSaved() { emit('reload') }
function onBulkSaved() { bulkPartyOpen.value = false; state.selected.clear(); emit('reload') }
```

---

## `RowsTable.vue` — render contract

Sticky header. Sticky-left columns: `row_idx`, `select`. Sticky-right
columns: `kebab`. Horizontal scroll on the middle band.

Renders rows by mapping `visibleColumns` over each row, dispatching per
`renderer`:

```vue
<template>
  <div class="overflow-x-auto border rounded-lg">
    <table class="min-w-full table-fixed">
      <thead class="sticky top-0 bg-surface z-10">
        <tr>
          <th v-for="cid in visibleColumns" :key="cid" :class="thClass(cid)">
            <ColumnHeader :col="colDef(cid)" :sort="sort" @sort="$emit('sort', $event)" />
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows" :key="row.row_idx"
          :class="rowClass(row)"
          @click="$emit('row-click', row)"
          @dblclick.stop="onPartyDblClick(row, $event)"
        >
          <CellRenderer
            v-for="cid in visibleColumns" :key="cid"
            :col="colDef(cid)"
            :row="row"
            :editable="editable"
            :selected="selected.has(row.row_idx)"
            @select-toggle="$emit('select-toggle', row.row_idx)"
            @inline-edit="$emit('inline-edit', { row_idx: row.row_idx, ...$event })"
            @row-action="$emit('row-action', { action: $event, row })"
          />
        </tr>
      </tbody>
    </table>
  </div>
</template>
```

`rowClass(row)` applies left-border colors per design brief:

```js
function rowClass(row) {
  return [
    row.validation_status === 'Error' ? 'border-l-2 border-l-danger' : '',
    row.validation_status === 'Skipped' ? 'border-l-2 border-l-warning' : '',
    row.is_duplicate ? 'opacity-70' : '',
    row.posted_docname ? 'border-l-2 border-l-success' : '',
    realtimePulseMap.value[row.row_idx] ? 'animate-pulse-once' : '',
  ].filter(Boolean).join(' ')
}
```

`CellRenderer.vue` (a switch component):

```vue
<script setup>
const props = defineProps({ col: Object, row: Object, editable: Boolean, selected: Boolean })
const emit = defineEmits(['select-toggle', 'inline-edit', 'row-action'])

const val = computed(() => props.row[props.col.field || props.col.id])
</script>

<template>
  <td :class="tdClass(col)">
    <input v-if="col.renderer === 'select-checkbox'" type="checkbox" :checked="selected" @change.stop="emit('select-toggle')" />

    <StatusPill v-else-if="col.renderer === 'status-pill'" :status="val" />

    <span v-else-if="col.renderer === 'date-short'" class="tabular-nums">{{ formatDateShort(val) }}</span>
    <span v-else-if="col.renderer === 'time-short'" class="tabular-nums">{{ formatTimeShort(val) }}</span>

    <AmountDisplay
      v-else-if="col.renderer === 'amount-signed'"
      :amount="signed(val, row[col.signFromField])"
      :currency="row[col.currencyField] || 'PKR'"
    />

    <TypePill v-else-if="col.renderer === 'type-pill'" :type="val" />

    <div v-else-if="col.renderer === 'category-with-sub'">
      <div>{{ val || '—' }}</div>
      <div v-if="row[col.subField]" class="text-xs text-ink-3">{{ row[col.subField] }}</div>
    </div>

    <span v-else-if="col.renderer === 'truncated'" class="line-clamp-1" :title="row[col.titleFromField]">{{ val }}</span>

    <a v-else-if="col.renderer === 'link-account'" :href="val ? `/app/account/${val}` : null"
       target="_blank" rel="noopener" class="text-link">{{ val || '—' }}</a>

    <a v-else-if="col.renderer === 'desk-link' && val" target="_blank" rel="noopener"
       :href="`/app/${slug(row[col.targetDoctypeField])}/${val}`" class="text-link tabular-nums">{{ val }}</a>
    <span v-else-if="col.renderer === 'desk-link'">—</span>

    <span v-else-if="col.renderer === 'check-icon'">
      <Check v-if="val" class="w-3 h-3 text-success" /><span v-else>—</span>
    </span>

    <InlinePartyEdit
      v-else-if="col.renderer === 'inline-party-edit'"
      :row="row"
      :editable="editable && col.editableWhen(row)"
      @save="payload => emit('inline-edit', payload)"
    />

    <span v-else-if="col.renderer === 'error-text'" class="text-danger text-xs line-clamp-2" :title="val">{{ val || '—' }}</span>

    <span v-else-if="col.renderer === 'code-badge'" class="px-2 py-0.5 rounded bg-surface-2 text-xs">{{ val || '' }}</span>

    <RevertCell v-else-if="col.renderer === 'revert-pill'" :status="val" :error="row[col.errorField]" />

    <RowKebabMenu v-else-if="col.renderer === 'row-kebab'" :row="row" :editable="editable" @action="a => emit('row-action', a)" />

    <span v-else class="tabular-nums">{{ val ?? '—' }}</span>
  </td>
</template>
```

Sort handled at `ColumnHeader.vue`; ascending/descending arrow on the
sortable headers.

---

## `InlinePartyEdit.vue`

```vue
<template>
  <div v-if="!editing" class="cursor-pointer" @dblclick="onActivate">
    <span v-if="row.resolved_party">
      {{ row.resolved_party }}
      <span class="text-xs text-ink-3">({{ row.resolved_party_type }})</span>
    </span>
    <span v-else-if="row.requires_party" class="text-danger text-xs">Set party</span>
    <span v-else class="text-ink-3">—</span>
  </div>
  <div v-else class="flex items-center gap-1">
    <select v-model="local.party_type" class="text-xs" @keydown.enter.prevent="onSave" @keydown.esc="onCancel" ref="typeRef">
      <option value="Customer">Customer</option>
      <option value="Supplier">Supplier</option>
      <option value="">None</option>
    </select>
    <Autocomplete
      v-if="local.party_type"
      v-model="local.party"
      :reference_doctype="local.party_type"
      reference_fieldname="default_party"
      class="text-xs flex-1"
      @keydown.enter.prevent="onSave"
      @keydown.esc="onCancel"
    />
    <Spinner v-if="saving" class="w-3 h-3" />
  </div>
</template>

<script setup>
const props = defineProps({ row: Object, editable: Boolean })
const emit = defineEmits(['save'])
const editing = ref(false)
const local = reactive({ party_type: '', party: '' })
const saving = ref(false)

function onActivate() {
  if (!props.editable) return
  local.party_type = props.row.resolved_party_type || ''
  local.party = props.row.resolved_party || ''
  editing.value = true
  nextTick(() => typeRef.value?.focus())
}

async function onSave() {
  saving.value = true
  try {
    await emit('save', { party_type: local.party_type, party: local.party })
    editing.value = false
  } finally { saving.value = false }
}

function onCancel() { editing.value = false }
</script>
```

`reference_fieldname="default_party"` is a stable Frappe convention for
Dynamic Link party fields; if `Cashew Import Row.resolved_party` is the
real field, the `reference_fieldname` should be that exact name —
verify on first install (D5 rule 2). If `set_query` was registered on
`resolved_party`, this will honor it.

---

## `ValidationFixModal.vue`

Triggered by row kebab → "Fix this row…" OR clicking the row's Error
pill.

```vue
<template>
  <Dialog v-model:open="open" title="Fix row" size="lg">
    <div class="space-y-3">
      <div class="rounded bg-surface-2 p-2 text-sm">
        <div class="text-danger font-medium">{{ row.validation_error_code }}</div>
        <div class="text-ink-2 text-xs">{{ row.validation_error_message }}</div>
      </div>

      <dl class="grid grid-cols-2 gap-y-1 text-sm">
        <dt class="text-ink-3">Date</dt>     <dd>{{ row.txn_date }}</dd>
        <dt class="text-ink-3">Account</dt>  <dd>{{ row.raw_account }}</dd>
        <dt class="text-ink-3">Amount</dt>   <dd><AmountDisplay :amount="row.base_amount" :currency="row.company_currency" /></dd>
        <dt class="text-ink-3">Type</dt>     <dd>{{ row.txn_type }}</dd>
        <dt class="text-ink-3">Category</dt> <dd>{{ row.category }}</dd>
      </dl>

      <FormField v-if="showAccount" label="Resolved Account">
        <Autocomplete v-model="form.resolved_account" reference_doctype="Cashew Import Row"
                      reference_fieldname="resolved_account" />
      </FormField>

      <FormField v-if="showExternal" label="External Account">
        <Autocomplete v-model="form.resolved_external_account" reference_doctype="Cashew Import Row"
                      reference_fieldname="resolved_external_account" />
      </FormField>

      <FormField v-if="showParty" label="Party Type">
        <select v-model="form.resolved_party_type">
          <option value="Customer">Customer</option>
          <option value="Supplier">Supplier</option>
        </select>
      </FormField>
      <FormField v-if="showParty && form.resolved_party_type" label="Party">
        <Autocomplete v-model="form.resolved_party" :reference_doctype="form.resolved_party_type"
                      reference_fieldname="default_party" />
      </FormField>
    </div>

    <template #footer>
      <Button variant="ghost" @click="$emit('close')">Cancel</Button>
      <Button variant="solid" theme="accent" :loading="saving" @click="onSave">Save & Re-validate</Button>
    </template>
  </Dialog>
</template>
```

`showAccount` / `showExternal` / `showParty` derived from `row.validation_error_code`:

```js
const SHOW_BY_CODE = {
  NO_ACCOUNT_MAP:   { account: true },
  NO_EXTERNAL_ACCT: { external: true },
  MISSING_PARTY:    { party: true },
  // unknown code → show all editable fields as a fallback
}
const flags = computed(() => SHOW_BY_CODE[row.validation_error_code]
  || { account: true, external: true, party: true })
const showAccount = computed(() => flags.value.account)
const showExternal = computed(() => flags.value.external)
const showParty = computed(() => flags.value.party)
```

`onSave`:
1. If any of `resolved_account` / `resolved_external_account` /
   `resolved_party_type` / `resolved_party` changed: write them. Account
   edits use the existing `cashew_integration.api.row_explorer_set_party`
   API for party fields; account fields use
   `frappe.client.set_value('Cashew Import Row', row.name,
   { resolved_account, resolved_external_account })`. (D5 rule 1: reads
   via frappe.client.*; writes via custom api.py — but `set_value` is
   the canonical write for field updates that don't need workflow.
   `Cashew Import Row.permissions` already inherit from `Cashew Import Run`;
   verify in c010 audit.)
2. Call `row_explorer_revalidate(run_name, [row_idx])`.
3. If new `validation_status === 'Valid'` → close modal + emit `saved`.
   Else → keep modal open, update local `row` from response, re-render
   with new error.

---

## `BulkPartyModal.vue`

```vue
<template>
  <Dialog v-model:open="open" :title="`Set party on ${count} rows`" size="md">
    <p class="text-sm text-ink-3 mb-3">Existing party values on selected rows will be overwritten.</p>
    <FormField label="Party Type">
      <select v-model="form.party_type">
        <option value="Customer">Customer</option>
        <option value="Supplier">Supplier</option>
      </select>
    </FormField>
    <FormField v-if="form.party_type" label="Party">
      <Autocomplete v-model="form.party" :reference_doctype="form.party_type" reference_fieldname="default_party" />
    </FormField>
    <template #footer>
      <Button variant="ghost" @click="$emit('close')">Cancel</Button>
      <Button
        variant="solid" theme="accent"
        :disabled="!form.party_type || !form.party"
        :loading="saving"
        @click="onSave"
      >
        Set party on {{ count }} rows
      </Button>
    </template>
  </Dialog>
</template>
```

`onSave`:
```js
await frappe.call('cashew_integration.api.row_explorer_set_party', {
  run_name: props.runName,
  row_indices: props.rowIndices,
  party_type: form.party_type,
  party: form.party,
})
toast(`Set party '${form.party}' on ${props.count} rows`)
emit('saved')
```

---

## `SelectionFooter.vue`

Fixed bottom (above mobile bottom-nav on `<md`), sticky bottom of
content on `>=md`. Slides in (translate-y) when selection set is
non-empty.

```vue
<template>
  <Transition name="slide-up">
    <div v-if="count > 0" class="fixed left-0 right-0 bottom-16 md:bottom-4 mx-auto max-w-2xl px-4 z-30">
      <div class="rounded-full bg-ink-1 text-ink-on-dark px-4 py-2 flex items-center gap-3 shadow-lg">
        <span class="text-sm">{{ count }} rows selected</span>
        <Button v-for="a in actions" :key="a.id" size="sm" variant="ghost"
                @click="$emit('action', a)">
          {{ a.label }}
        </Button>
        <Button size="sm" variant="ghost" @click="$emit('clear')">Clear</Button>
      </div>
    </div>
  </Transition>
</template>
```

---

## `InlineRowDrawer.vue`

Right-side drawer (frappe-ui `<Drawer>` if available, else absolute
positioned panel). Shows all 30+ `Cashew Import Row` fields read-only,
plus a "View raw JSON" toggle that pretty-prints the entire row.

Non-destructive — closes via `Esc` or backdrop click.

---

## `RowKebabMenu.vue`

```js
const items = computed(() => [
  { label: 'Fix this row…',  icon: 'wrench',     show: props.row.validation_status === 'Error' && props.editable, action: 'fix' },
  { label: 'Re-validate row',icon: 'rotate-cw',  show: props.editable, action: 'revalidate' },
  { label: 'View row JSON',  icon: 'code',       show: true, action: 'view-json' },
  { label: 'Open posted doc',icon: 'external-link', show: !!props.row.posted_docname, action: 'open-posted' },
].filter(i => i.show))
```

Emits `@action="action"` upstream → handled in workbench.

---

## Mobile variant — `RowsCardList.vue` + `RowCard.vue`

`<640px`. Each row → card with: Sr + Date + Amount + Type + Category +
Validation pill + Party.

Long-press → enters selection mode (cards get checkmark; SelectionFooter
slides up). Tap → opens InlineRowDrawer. Tap-and-hold on Party text →
opens ValidationFixModal (since dblclick isn't a mobile gesture).

ValidationFixModal becomes full-screen sheet (`size="full"`) on mobile.

---

## Per-run realtime patching

c008's `subscribeDoc('Cashew Import Run', runName, callback)` emits
events. When event includes per-row patches:

```js
function onRealtimeEvent(event) {
  if (event.doc) patchDoc(event.doc)
  if (event.rows) {
    event.rows.forEach(r => {
      patchRow(r.row_idx, r)
      realtimePulseMap.value[r.row_idx] = Date.now() + 500   // pulse 500ms
    })
  }
}
```

`patchRow` lives in `useRun` (c006-spec.md). `realtimePulseMap` is a
local reactive map in RowsWorkbench; rowClass reads it for the
`animate-pulse-once` class.

---

## Acceptance (workbench)

- [ ] Workbench renders at status Validated / Queued / Processing.
- [ ] Toolbar shows Search, Filters, Columns, Bulk actions, Validate.
- [ ] Search input debounces 250ms; multi-word AND across visible
      string columns; matches in hidden columns auto-extend the visible
      preset (set `state.searchExtendsVisible = true`; merge matching
      columns into `state.visibleColumns`).
- [ ] All 8 filter facets work; each renders a chip in
      ActiveFilterChips when active; chip × removes it; Clear all
      empties `state.filters`.
- [ ] Column dropdown lists 4 presets + every column with a toggle;
      "Reset to preset" restores preset columns.
- [ ] Default preset on mount = `Validation-focused` when any row has
      `validation_status === 'Error'`, else `Posting-focused` (Validated)
      or `Compact`.
- [ ] Row click opens InlineRowDrawer with all fields read-only.
- [ ] Party cell dblclick activates InlinePartyEdit; Tab moves Type ↔
      Party; Enter saves; Esc cancels; spinner during save.
- [ ] Row kebab shows Fix / Re-validate / View JSON / Open posted doc
      conditionally.
- [ ] ValidationFixModal opens; editable fields conditional on
      `validation_error_code`; Save & Re-validate calls
      `row_explorer_revalidate` and closes on Valid; stays open with
      new error on persistent error.
- [ ] Bulk select via row-checkbox; header checkbox selects all
      filtered rows.
- [ ] SelectionFooter shows count + actions; Set party… opens
      BulkPartyModal; Re-validate selected calls
      `row_explorer_revalidate`; Clear empties selection.
- [ ] BulkPartyModal saves all selected rows; toast confirms count.
- [ ] Sort works on sortable columns; default = row_idx asc.
- [ ] Row color cues: Error red border-left, Skipped grey, posted
      green, duplicate faded.
- [ ] Realtime: row patch triggers `animate-pulse-once` (500ms).
- [ ] Read-mostly mode (Queued/Processing): inline-edit disabled,
      bulk-write actions hidden, Validate button hidden, kebab "Fix"
      hidden, Re-validate hidden.
- [ ] Mobile (`<640px`): cards instead of table; long-press selects;
      ValidationFixModal full-screen.
- [ ] No `localStorage` / `sessionStorage` writes — grep zero hits.

---

## TD calls inside arch envelope (not surfacing)

- **Renderer-by-string in CellRenderer.vue.** Avoids 25+ tiny SFCs; one
  large but boring switch component. New renderers added in one place.
- **D11 declarative registries land in three files** (columns/filters/
  bulkActions). New features extend these without touching the
  workbench component.
- **`Cashew Import Row.set_value` for account fields in
  ValidationFixModal.** D5 rule 1 says reads via frappe.client.*; the
  rule for writes is "reuse api.py whitelisted methods". `set_value`
  for a simple field write is the canonical Frappe path; the c010
  audit adds `has_permission` checks if missing. If a future
  validator hook needs to run on save, switch to a dedicated whitelist
  method.
- **Long-press / mobile selection mode** — chosen over a permanently-
  visible checkbox on mobile cards because most mobile traffic is
  read-only check-ins (status-watching), not bulk edits.
- **`reference_fieldname="default_party"` placeholder** — verify exact
  fieldname on first install. If `Cashew Import Row.resolved_party` is
  what we want to bind, that's the value to use.
- **Pulse keyframe via `animate-pulse-once`** — same Tailwind keyframe
  added by c005. One definition, two consumers.

---

## Open items (handed off)

- **`reference_fieldname` for the resolved_party Autocomplete** —
  c010 audit confirms exact fieldname or registers a `set_query`.
- **Drawer component availability in frappe-ui** — Dev confirms; fall
  back to absolute panel if missing.
- **`Cashew Import Row` permissions inheriting from `Cashew Import Run`**
  — c010 verifies; if not, ValidationFixModal needs a server-side
  endpoint that authorizes via the parent run.
- **Search-extends-visible UX** — when search hits a hidden column,
  add the column temporarily AND clear the addition when search
  clears. State flag `searchExtendsVisible` tracks the temporary set.
- **Cancel during Processing** — `cancel_run` semantics: does it
  abort the current job or just flip status? Verify on first run;
  surface user-facing copy accordingly.
