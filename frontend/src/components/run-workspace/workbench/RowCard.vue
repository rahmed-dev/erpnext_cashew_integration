<script setup>
import { Button } from 'frappe-ui';
import StatusPill from '@/components/shared/StatusPill.vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';
import RowKebabMenu from './RowKebabMenu.vue';

defineProps({
  row: { type: Object, required: true },
  selected: { type: Boolean, default: false },
  editable: { type: Boolean, default: true },
  pulse: { type: Boolean, default: false },
});
const emit = defineEmits(['select-toggle', 'row-action', 'row-click']);
</script>

<template>
  <article
    :class="[
      'rounded-lg border border-gray-200 bg-white p-3',
      row.validation_status === 'Error' && 'border-l-2 border-l-red-500',
      row.validation_status === 'Skipped' && 'border-l-2 border-l-amber-500',
      row.is_duplicate && 'opacity-60',
      pulse && 'animate-pulse-once',
    ]"
    @click="emit('row-click', row)"
  >
    <header class="flex items-start gap-2">
      <input type="checkbox" class="rounded border-gray-300 text-[var(--cs-accent)] focus:ring-[var(--cs-accent)]" :checked="selected" @click.stop @change="emit('select-toggle', row.row_idx)" />
      <span class="text-xs text-gray-500 tabular-nums">#{{ row.row_idx }}</span>
      <span class="ml-auto inline-flex items-center gap-1">
        <StatusPill kind="row-validation" :value="row.validation_status" />
        <RowKebabMenu :row="row" :editable="editable" @action="(p) => emit('row-action', p)" />
      </span>
    </header>

    <div class="mt-2 flex items-baseline justify-between gap-2">
      <div class="text-sm text-gray-900 truncate min-w-0">{{ row.raw_account || '—' }}</div>
      <div class="text-right shrink-0">
        <AmountDisplay :amount="row.base_amount" :currency="row.company_currency || 'PKR'" :signed="true" />
        <div
          v-if="row.source_currency && row.source_currency !== (row.company_currency || 'PKR')"
          class="text-xs text-gray-500"
        >
          <AmountDisplay :amount="row.raw_amount" :currency="row.source_currency" />
        </div>
      </div>
    </div>

    <div class="mt-1.5 flex items-center gap-2 text-xs text-gray-500">
      <span>{{ row.txn_date || '—' }}</span>
      <StatusPill v-if="row.txn_type" kind="txn-type" :value="row.txn_type" />
      <span v-if="row.category" class="truncate min-w-0">· {{ row.category }}</span>
    </div>

    <p v-if="row.validation_error_message" class="text-xs text-red-700 mt-1 line-clamp-2">{{ row.validation_error_message }}</p>

    <div v-if="editable && row.validation_status === 'Error'" class="mt-2">
      <Button variant="subtle" theme="red" size="sm" @click.stop="emit('row-action', { action: 'fix', row })">Fix this row</Button>
    </div>
  </article>
</template>
