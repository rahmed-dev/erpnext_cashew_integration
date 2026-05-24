<script setup>
import { computed } from 'vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';

const props = defineProps({
  items: { type: Array, default: () => [] },
});

// Sort key + bar widths use base_amount (company currency) so a USD
// account sorts above a smaller PKR account when its PKR equivalent is bigger.
const baseTotal = computed(() =>
  props.items.reduce((s, i) => s + Math.abs(i.base_amount ?? i.amount ?? 0), 0),
);

function barPct(it) {
  const v = Math.abs(it.base_amount ?? it.amount ?? 0);
  if (baseTotal.value <= 0) return 0;
  return Math.max(2, Math.round((v / baseTotal.value) * 100));
}

function isForeign(it) {
  return !!(it.base_currency && it.currency && it.base_currency !== it.currency);
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-5">
    <header class="mb-3">
      <h3 class="text-sm font-semibold text-gray-900">Top assets</h3>
      <p class="text-xs text-gray-500">From Chart of Accounts · closing balance · up to 10 · sorted by base-currency value</p>
    </header>

    <div v-if="items.length === 0" class="text-xs text-gray-400 italic py-4">
      No asset balances to show.
    </div>

    <ul v-else class="space-y-2">
      <li v-for="(it, i) in items" :key="i">
        <div class="flex items-center justify-between text-xs mb-0.5 gap-2">
          <span class="truncate min-w-0 text-gray-700">{{ it.account }}</span>
          <span class="shrink-0 text-right">
            <span class="inline-flex items-baseline gap-1.5">
              <AmountDisplay
                :amount="it.amount"
                :currency="it.currency"
                class="font-medium tabular-nums text-gray-900"
                :signed="(it.amount || 0) < 0"
              />
              <span class="text-[10px] text-gray-400 uppercase tracking-wide">{{ it.currency }}</span>
            </span>
            <div v-if="isForeign(it)" class="text-[10px] text-gray-400 tabular-nums">
              ≈ <AmountDisplay :amount="it.base_amount" :currency="it.base_currency" :signed="(it.base_amount || 0) < 0" />
            </div>
          </span>
        </div>
        <div class="h-1.5 rounded bg-gray-100 overflow-hidden">
          <div
            class="h-full"
            :style="`width: ${barPct(it)}%; background: var(--cs-accent);`"
          />
        </div>
      </li>
    </ul>
  </div>
</template>
