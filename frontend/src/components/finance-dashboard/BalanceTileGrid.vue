<script setup>
import { Wallet, ArrowDownToLine, ArrowUpFromLine, TrendingUp } from 'lucide-vue-next';
import BalanceTile from './BalanceTile.vue';

defineProps({
  data: { type: [Object, null], default: null },
  currency: { type: String, default: 'PKR' },
  breakdowns: { type: Object, default: () => ({}) },
});
defineEmits(['tile-click']);

const TILES = [
  { id: 'cash_bank',      label: 'Cash & Bank',      icon: Wallet,           invert: false, clickable: true  },
  { id: 'receivable',     label: 'Receivable',       icon: ArrowDownToLine,  invert: false, clickable: true  },
  { id: 'payable',        label: 'Payable',          icon: ArrowUpFromLine,  invert: true,  clickable: true  },
  { id: 'net_for_period', label: 'Net for Period',   icon: TrendingUp,       invert: false, clickable: false, noDelta: true },
];
</script>

<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
    <BalanceTile
      v-for="t in TILES"
      :key="t.id"
      :tile-id="t.id"
      :label="t.label"
      :icon="t.icon"
      :amount="data?.[t.id]?.amount"
      :prior="t.noDelta ? null : data?.[t.id]?.prior_amount"
      :currency="currency"
      :loading="!data"
      :invert="t.invert"
      :clickable="t.clickable"
      :breakdown="breakdowns?.[t.id] || null"
      @click="$emit('tile-click', t.id)"
    />
  </div>
</template>
