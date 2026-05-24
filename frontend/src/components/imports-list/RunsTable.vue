<script setup>
import RunRow from './RunRow.vue';
import SkeletonBlock from '@/components/shared/SkeletonBlock.vue';
import { ChevronUp, ChevronDown } from 'lucide-vue-next';

const props = defineProps({
  rows: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  sort: { type: Object, required: true },
  pulseMap: { type: Object, default: () => ({}) },
});
const emit = defineEmits(['sort', 'action']);

const COLUMNS = [
  { key: 'name',         label: 'Run',         sortable: false, cls: '' },
  { key: 'status',       label: 'Status',      sortable: true, cls: '' },
  { key: 'company',      label: 'Company',     sortable: false, cls: 'hidden lg:table-cell' },
  { key: 'period_start', label: 'Period',      sortable: true, cls: '' },
  { key: 'rows_total',   label: 'Total',       sortable: false, cls: 'text-right hidden sm:table-cell' },
  { key: 'rows_valid',   label: 'Valid',       sortable: false, cls: 'text-right hidden md:table-cell' },
  { key: 'rows_failed',  label: 'Failed',      sortable: false, cls: 'text-right hidden md:table-cell' },
  { key: 'rows_posted',  label: 'Posted',      sortable: false, cls: 'text-right hidden lg:table-cell' },
  { key: 'rows_skipped', label: 'Skipped',     sortable: false, cls: 'text-right hidden lg:table-cell' },
  { key: 'modified',     label: 'Updated',     sortable: true, cls: '' },
];

function toggleSort(col) {
  if (!col.sortable) return;
  if (props.sort.column === col.key) {
    emit('sort', { column: col.key, dir: props.sort.dir === 'asc' ? 'desc' : 'asc' });
  } else {
    emit('sort', { column: col.key, dir: 'desc' });
  }
}
</script>

<template>
  <div class="border border-gray-200 rounded-lg overflow-hidden bg-white">
    <table class="w-full text-sm border-collapse">
      <thead class="bg-gray-50 sticky top-0">
        <tr>
          <th
            v-for="c in COLUMNS"
            :key="c.key"
            scope="col"
            :class="['text-[11px] uppercase tracking-wider font-semibold text-gray-600 px-3 py-2 text-left', c.cls, c.sortable ? 'cursor-pointer select-none' : '']"
            @click="toggleSort(c)"
          >
            <span class="inline-flex items-center gap-1">
              {{ c.label }}
              <ChevronUp v-if="c.sortable && sort.column === c.key && sort.dir === 'asc'" :size="12" />
              <ChevronDown v-else-if="c.sortable && sort.column === c.key && sort.dir === 'desc'" :size="12" />
            </span>
          </th>
          <th aria-label="Actions" class="w-8"></th>
        </tr>
      </thead>
      <tbody>
        <template v-if="loading && !rows.length">
          <tr v-for="i in 5" :key="`sk-${i}`" class="border-b border-gray-100">
            <td colspan="11" class="px-3 py-3">
              <SkeletonBlock shape="line" height="14px" />
            </td>
          </tr>
        </template>
        <template v-else>
          <RunRow
            v-for="row in rows"
            :key="row.name"
            :row="row"
            :pulse="!!pulseMap[row.name]"
            @action="(e) => emit('action', e)"
          />
        </template>
      </tbody>
    </table>
  </div>
</template>
