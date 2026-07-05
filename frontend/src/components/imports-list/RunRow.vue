<script setup>
import { useRouter } from 'vue-router';
import StatusPill from '@/components/shared/StatusPill.vue';
import DateRange from '@/components/shared/DateRange.vue';
import RowKebabMenu from './RowKebabMenu.vue';

const props = defineProps({
  row: { type: Object, required: true },
  pulse: { type: Boolean, default: false },
});
const emit = defineEmits(['action']);

const router = useRouter();
function open() { router.push(`/runs/${props.row.name}`); }
function formatModified(s) {
  if (!s) return '—';
  const d = new Date(s.replace(' ', 'T'));
  if (Number.isNaN(+d)) return s;
  return d.toLocaleString('en-PK', { dateStyle: 'medium', timeStyle: 'short' });
}
</script>

<template>
  <tr
    class="border-b border-gray-100 hover:bg-gray-50 cursor-pointer transition-colors"
    :class="pulse ? 'pulse-row' : ''"
    @click="open"
  >
    <td class="px-3 py-2.5 font-mono text-xs text-gray-900">{{ row.name }}</td>
    <td class="px-3 py-2.5">
      <div class="flex items-center gap-1.5">
        <StatusPill kind="run-status" :value="row.status" size="sm" />
        <StatusPill v-if="row.source_type" kind="source-type" :value="row.source_type" size="sm" />
      </div>
    </td>
    <td class="px-3 py-2.5 hidden lg:table-cell text-sm text-gray-700 truncate max-w-[160px]">{{ row.company || '—' }}</td>
    <td class="px-3 py-2.5 text-sm"><DateRange :start="row.period_start" :end="row.period_end" /></td>
    <td class="px-3 py-2.5 text-sm text-right tabular-nums hidden sm:table-cell">{{ row.rows_total ?? '—' }}</td>
    <td class="px-3 py-2.5 text-sm text-right tabular-nums hidden md:table-cell">{{ row.rows_valid ?? '—' }}</td>
    <td class="px-3 py-2.5 text-sm text-right tabular-nums hidden md:table-cell text-red-700">{{ row.rows_failed ?? '—' }}</td>
    <td class="px-3 py-2.5 text-sm text-right tabular-nums hidden lg:table-cell">{{ row.rows_posted ?? '—' }}</td>
    <td class="px-3 py-2.5 text-sm text-right tabular-nums hidden lg:table-cell text-gray-500">{{ row.rows_skipped ?? '—' }}</td>
    <td class="px-3 py-2.5 text-xs text-gray-500 whitespace-nowrap">{{ formatModified(row.modified) }}</td>
    <td class="px-2 py-2.5 text-right">
      <RowKebabMenu :row="row" @action="(e) => emit('action', e)" />
    </td>
  </tr>
</template>

<style scoped>
.pulse-row {
  animation: cs-pulse-once 500ms ease-out;
}
@keyframes cs-pulse-once {
  0%   { background-color: var(--cs-accent-50); }
  100% { background-color: transparent; }
}
@media (prefers-reduced-motion: reduce) {
  .pulse-row { animation: none; }
}
</style>
