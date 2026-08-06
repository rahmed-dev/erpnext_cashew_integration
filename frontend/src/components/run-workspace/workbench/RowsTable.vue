<script setup>
import { computed } from 'vue';
import { Button } from 'frappe-ui';
import { COLUMN_DEFS, colDef } from './registries/columns';

import StatusPill from '@/components/shared/StatusPill.vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';
import InlinePartyEdit from './InlinePartyEdit.vue';
import RowKebabMenu from './RowKebabMenu.vue';
import { ChevronUp, ChevronDown, ExternalLink, ArrowUpDown } from 'lucide-vue-next';

const props = defineProps({
  rows: { type: Array, default: () => [] },
  visibleColumns: { type: Array, required: true },
  selected: { type: Set, default: () => new Set() },
  editable: { type: Boolean, default: true },
  runName: { type: [String, null], default: null },
  sort: { type: [Object, null], default: null },
  recentPatches: { type: Set, default: () => new Set() },
});
const emit = defineEmits(['select-toggle', 'select-all', 'row-action', 'row-click', 'sort', 'row-saved']);

const allSelected = computed(() => props.rows.length > 0 && props.rows.every((r) => props.selected.has(r.row_idx)));

function header(id) { return colDef(id); }

function thClass(col) {
  return [
    'px-2 py-1.5 text-left text-[10px] uppercase tracking-wide font-semibold text-gray-500 bg-gray-50 whitespace-nowrap',
    col.sticky === 'left' && 'sticky left-0 z-10',
    col.sticky === 'right' && 'sticky right-0 z-10',
    col.align === 'right' && 'text-right',
  ];
}

function tdClass(col, row) {
  return [
    'px-2 py-1.5 text-sm',
    col.sticky === 'left' && 'sticky left-0 bg-white',
    col.sticky === 'right' && 'sticky right-0 bg-white',
    col.align === 'right' && 'text-right',
    col.tabular && 'tabular-nums',
  ];
}

function rowClass(row) {
  return [
    'border-t border-gray-100 hover:bg-gray-50/60 cursor-pointer',
    row.validation_status === 'Error' && 'border-l-2 border-l-red-500',
    row.validation_status === 'Skipped' && 'border-l-2 border-l-amber-500',
    row.is_duplicate && 'opacity-60',
    props.recentPatches.has(row.row_idx) && 'animate-pulse-once',
  ];
}

function toggleSort(col) {
  if (!col.sortable) return;
  if (props.sort?.column === col.id) {
    emit('sort', { column: col.id, dir: props.sort.dir === 'asc' ? 'desc' : null });
  } else {
    emit('sort', { column: col.id, dir: 'asc' });
  }
}

function onHeaderSelectAll() {
  emit('select-all', !allSelected.value);
}
</script>

<template>
  <div class="overflow-x-auto rounded-lg border border-gray-200 bg-white relative">
    <table class="min-w-full text-sm">
      <thead class="sticky top-0 z-10">
        <tr>
          <th
            v-for="cid in visibleColumns"
            :key="cid"
            :class="thClass(header(cid))"
            @click="header(cid)?.sortable && toggleSort(header(cid))"
          >
            <template v-if="header(cid)?.renderer === 'select-checkbox'">
              <input type="checkbox" class="rounded border-gray-300 text-[var(--cs-accent)] focus:ring-[var(--cs-accent)]" :checked="allSelected" @change="onHeaderSelectAll" />
            </template>
            <template v-else>
              <span class="inline-flex items-center gap-1">
                {{ header(cid)?.header }}
                <template v-if="header(cid)?.sortable">
                  <ChevronUp v-if="sort?.column === cid && sort.dir === 'asc'" :size="11" />
                  <ChevronDown v-else-if="sort?.column === cid && sort.dir === 'desc'" :size="11" />
                  <ArrowUpDown v-else :size="11" class="opacity-40" />
                </template>
              </span>
            </template>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in rows"
          :key="row.row_idx"
          :class="rowClass(row)"
          @click="emit('row-click', row)"
        >
          <td
            v-for="cid in visibleColumns"
            :key="cid"
            :class="tdClass(header(cid), row)"
            @click.stop
          >
            <template v-if="header(cid).renderer === 'select-checkbox'">
              <input
                type="checkbox"
                class="rounded border-gray-300 text-[var(--cs-accent)] focus:ring-[var(--cs-accent)]"
                :checked="selected.has(row.row_idx)"
                @change="emit('select-toggle', row.row_idx)"
                @click.stop
              />
            </template>
            <template v-else-if="header(cid).renderer === 'validation-pill'">
              <StatusPill kind="row-validation" :value="row.validation_status" />
            </template>
            <template v-else-if="header(cid).renderer === 'type-pill'">
              <StatusPill v-if="row.txn_type" kind="txn-type" :value="row.txn_type" />
              <span v-else class="text-gray-400">—</span>
            </template>
            <template v-else-if="header(cid).renderer === 'date-short'">
              {{ row.txn_date || '—' }}
            </template>
            <template v-else-if="header(cid).renderer === 'amount-signed'">
              <AmountDisplay :amount="row.base_amount" :currency="row.company_currency || 'PKR'" :signed="true" />
              <div
                v-if="row.source_currency && row.source_currency !== (row.company_currency || 'PKR')"
                class="text-xs text-gray-500"
                :title="`Original amount in ${row.source_currency}`"
              >
                <AmountDisplay :amount="row.raw_amount" :currency="row.source_currency" />
              </div>
            </template>
            <template v-else-if="header(cid).renderer === 'category-with-sub'">
              <div class="text-sm">{{ row.category || '—' }}</div>
              <div v-if="row.sub_category" class="text-xs text-gray-500">{{ row.sub_category }}</div>
            </template>
            <template v-else-if="header(cid).renderer === 'truncated'">
              <span class="line-clamp-2 max-w-[24ch]" :title="row[header(cid).field]">{{ row[header(cid).field] || '' }}</span>
            </template>
            <template v-else-if="header(cid).renderer === 'error-text'">
              <span class="text-xs text-red-700 line-clamp-2" :title="row.validation_error_message">{{ row.validation_error_message || '' }}</span>
            </template>
            <template v-else-if="header(cid).renderer === 'party-edit'">
              <InlinePartyEdit :row="row" :run-name="runName" :editable="editable" @saved="emit('row-saved')" />
            </template>
            <template v-else-if="header(cid).renderer === 'posted-link'">
              <a
                v-if="row.posted_docname"
                class="inline-flex items-center gap-1 text-[var(--cs-accent)] hover:underline text-xs"
                :href="`/app/${(row.posted_doctype || '').toLowerCase().replace(/ /g, '-')}/${row.posted_docname}`"
                target="_blank"
                @click.stop
              >
                {{ row.posted_docname }}
                <ExternalLink :size="11" />
              </a>
              <span v-else class="text-gray-400">—</span>
            </template>
            <template v-else-if="header(cid).renderer === 'revert-pill'">
              <span v-if="!row.revert_status" class="text-gray-400">—</span>
              <!-- Shared pill, not a local class map: the local one keyed off
                   'Failed' and 'Pending', which are not values this field can hold
                   (the doctype has Reverted / Revert-Failed / Cancelled Externally /
                   Deleted Externally / Resynced / Superseded), so every real state
                   but 'Reverted' rendered unstyled. -->
              <span v-else :title="row.revert_error">
                <StatusPill kind="row-revert" :value="row.revert_status" />
              </span>
            </template>
            <template v-else-if="header(cid).renderer === 'row-kebab'">
              <div class="flex items-center justify-end gap-1">
                <Button
                  v-if="editable && row.validation_status === 'Error'"
                  variant="subtle"
                  theme="red"
                  size="sm"
                  @click.stop="emit('row-action', { action: 'fix', row })"
                >Fix</Button>
                <RowKebabMenu :row="row" :editable="editable" @action="(p) => emit('row-action', p)" />
              </div>
            </template>
            <template v-else>
              <span :class="header(cid).tabular ? 'tabular-nums' : ''">{{ row[header(cid).field] ?? '—' }}</span>
            </template>
          </td>
        </tr>
        <tr v-if="rows.length === 0">
          <td :colspan="visibleColumns.length" class="px-3 py-6 text-center text-sm text-gray-500">No rows match the current filters.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
