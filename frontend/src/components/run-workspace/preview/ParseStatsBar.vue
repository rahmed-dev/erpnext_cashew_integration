<script setup>
import { computed } from 'vue';
import { formatRange } from '@/utils/period';

const props = defineProps({
  doc: { type: Object, required: true },
  rows: { type: Array, default: () => [] },
});

const counts = computed(() => {
  const c = { income: 0, expense: 0, transfer: 0, loan: 0, adjust: 0, dup: 0 };
  for (const r of props.rows) {
    if (r.txn_type === 'Income') c.income += 1;
    else if (r.txn_type === 'Expense') c.expense += 1;
    else if (['Transfer', 'External Transfer'].includes(r.txn_type)) c.transfer += 1;
    else if (['Loan Receivable', 'Loan Payable'].includes(r.txn_type)) c.loan += 1;
    else if (r.txn_type === 'Adjustment') c.adjust += 1;
    if (r.is_duplicate) c.dup += 1;
  }
  return c;
});

const period = computed(() => formatRange(props.doc?.period_start, props.doc?.period_end) || '—');

const tiles = computed(() => {
  const t = [
    { label: 'Total rows', value: props.rows.length, always: true },
    { label: 'Period', value: period.value, always: true, wide: true },
    { label: 'Income', value: counts.value.income },
    { label: 'Expense', value: counts.value.expense },
    { label: 'Transfers', value: counts.value.transfer },
    { label: 'Loans', value: counts.value.loan },
    { label: 'Adjustments', value: counts.value.adjust },
    { label: 'Duplicates', value: counts.value.dup, danger: true },
  ];
  return t.filter((tile) => tile.always || tile.value > 0);
});
</script>

<template>
  <div class="flex flex-wrap gap-3">
    <div
      v-for="tile in tiles"
      :key="tile.label"
      :class="[
        'rounded border border-gray-200 px-3 py-2 bg-white',
        tile.wide ? 'min-w-[220px]' : 'min-w-[120px]',
      ]"
    >
      <div class="text-[10px] uppercase tracking-wide text-gray-500">{{ tile.label }}</div>
      <div :class="['text-base font-semibold', tile.danger && 'text-red-700']">{{ tile.value }}</div>
    </div>
  </div>
</template>
