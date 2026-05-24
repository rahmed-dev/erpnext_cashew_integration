<script setup>
import { computed, watch } from 'vue';
import { Dialog, createResource } from 'frappe-ui';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';

const props = defineProps({
  open: { type: Boolean, default: false },
  tile: { type: [String, null], default: null },
  company: { type: [String, null], default: null },
  asOf: { type: [String, null], default: null },
});
const emit = defineEmits(['update:open']);

const TITLES = {
  cash_bank:  { title: 'Cash & Bank balances',   subtitle: 'Per account · balance in account currency' },
  receivable: { title: 'Receivable by party',    subtitle: 'Per customer · balance in account currency' },
  payable:    { title: 'Payable by party',       subtitle: 'Per supplier · balance in account currency' },
};

const detail = createResource({
  url: 'cashew_integration.api.balance_tile_detail',
  cache: false,
  auto: false,
  makeParams: () => ({
    company: props.company,
    tile: props.tile,
    as_of: props.asOf,
  }),
});

watch(
  () => [props.open, props.tile, props.company, props.asOf],
  ([open]) => {
    if (open && props.tile && props.company && props.asOf) detail.reload();
  },
  { immediate: true },
);

const meta = computed(() => TITLES[props.tile] || { title: 'Balance details', subtitle: '' });
const items = computed(() => detail.data?.items || []);
const isPartyTile = computed(() => props.tile === 'receivable' || props.tile === 'payable');
const companyCurrency = computed(() => detail.data?.company_currency || '');

function isForeign(it) {
  return !!(companyCurrency.value && it.currency && companyCurrency.value !== it.currency);
}
</script>

<template>
  <Dialog :modelValue="open" @update:modelValue="(v) => emit('update:open', v)" :options="{ size: 'lg' }">
    <template #body>
      <div class="p-5">
        <header class="mb-4">
          <h2 class="text-base font-semibold text-gray-900">{{ meta.title }}</h2>
          <p class="text-xs text-gray-500 mt-0.5">{{ meta.subtitle }} · as of {{ asOf }}</p>
        </header>

        <div v-if="detail.loading" class="text-xs text-gray-500 py-10 text-center">Loading…</div>

        <div v-else-if="items.length === 0" class="text-xs text-gray-400 italic py-10 text-center">
          No open balances to show.
        </div>

        <ul v-else class="divide-y divide-gray-100 max-h-[60vh] overflow-y-auto -mx-1">
          <li v-for="(it, i) in items" :key="i" class="px-1 py-2.5 flex items-center justify-between gap-3">
            <div class="min-w-0">
              <template v-if="isPartyTile">
                <div class="text-sm text-gray-900 truncate">{{ it.party }}</div>
                <div class="text-[11px] text-gray-500 mt-0.5">{{ it.party_type }}</div>
              </template>
              <template v-else>
                <div class="text-sm text-gray-900 truncate">{{ it.account }}</div>
                <div class="text-[11px] text-gray-500 mt-0.5">{{ it.account_type }}</div>
              </template>
            </div>
            <div class="text-right shrink-0">
              <AmountDisplay
                :amount="it.balance"
                :currency="it.currency"
                class="font-semibold tabular-nums text-gray-900"
              />
              <div class="text-[10px] text-gray-400 uppercase tracking-wide mt-0.5">{{ it.currency }}</div>
              <div v-if="isForeign(it) && it.base_balance != null" class="text-[10px] text-gray-400 tabular-nums mt-0.5">
                ≈ <AmountDisplay :amount="it.base_balance" :currency="it.base_currency || companyCurrency" />
              </div>
            </div>
          </li>
        </ul>
      </div>
    </template>
  </Dialog>
</template>
