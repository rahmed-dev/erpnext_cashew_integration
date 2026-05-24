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
</script>

<template>
  <article
    class="border border-gray-200 rounded-lg p-3.5 bg-white space-y-2 cursor-pointer"
    :class="pulse ? 'pulse-card' : ''"
    @click="open"
  >
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0">
        <div class="font-mono text-xs text-gray-900 truncate">{{ row.name }}</div>
        <div class="text-[11px] text-gray-500 truncate">{{ row.company || '—' }}</div>
      </div>
      <StatusPill kind="run-status" :value="row.status" size="sm" />
    </div>
    <div class="text-[12px] text-gray-600">
      <DateRange :start="row.period_start" :end="row.period_end" />
    </div>
    <div class="flex items-center justify-between text-[12px] tabular-nums">
      <span><span class="text-gray-500">Total</span> {{ row.rows_total ?? 0 }}</span>
      <span class="text-red-700"><span class="text-gray-500">Failed</span> {{ row.rows_failed ?? 0 }}</span>
      <span><span class="text-gray-500">Posted</span> {{ row.rows_posted ?? 0 }}</span>
    </div>
    <div class="flex justify-end">
      <RowKebabMenu :row="row" @action="(e) => emit('action', e)" />
    </div>
  </article>
</template>

<style scoped>
.pulse-card {
  animation: cs-pulse-once 500ms ease-out;
}
@keyframes cs-pulse-once {
  0%   { box-shadow: 0 0 0 2px var(--cs-accent-100); }
  100% { box-shadow: 0 0 0 0 transparent; }
}
@media (prefers-reduced-motion: reduce) {
  .pulse-card { animation: none; }
}
</style>
