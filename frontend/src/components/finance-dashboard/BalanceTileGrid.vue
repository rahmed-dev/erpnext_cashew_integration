<script setup>
import { computed } from 'vue';
import {
  Wallet, ArrowDownToLine, ArrowUpFromLine, TrendingUp,
  Receipt, FileText, FileInput,
} from 'lucide-vue-next';
import BalanceTile from './BalanceTile.vue';

// f012 c003 — the KPI row extends this grid rather than adding a second card
// system beside it. Balance tiles and KPI tiles are the same object to the user:
// one number, one period, one glance.
const props = defineProps({
  data: { type: [Object, null], default: null },
  currency: { type: String, default: 'PKR' },
  breakdowns: { type: Object, default: () => ({}) },
  // Period expense, taken from `dashboard_summary.expense_total` — the SAME
  // scalar the rest of the tile row uses. The trend chart's own totals net
  // reversing postings where these clamp each GL row at zero, so the two must
  // never be shown as competing figures for one thing (f012 c002 note).
  expense: { type: [Number, null], default: null },
  // `dashboard_summary.invoices`: {sales, purchase}, each {count, amount} or
  // null when the user cannot read that doctype. A null HIDES its tile — a
  // permission gap must not render as a zero.
  invoices: { type: [Object, null], default: null },
});
defineEmits(['tile-click']);

const BALANCE_TILES = [
  { id: 'cash_bank',      label: 'Cash & Bank',    icon: Wallet,          invert: false, clickable: true  },
  { id: 'receivable',     label: 'Receivable',     icon: ArrowDownToLine, invert: false, clickable: true  },
  { id: 'payable',        label: 'Payable',        icon: ArrowUpFromLine, invert: true,  clickable: true  },
  { id: 'net_for_period', label: 'Net for Period', icon: TrendingUp,      invert: false, clickable: false, noDelta: true },
];

function invoiceCaption(block) {
  const n = block?.count || 0;
  return `${n} invoice${n === 1 ? '' : 's'} posted`;
}

const kpiTiles = computed(() => {
  const out = [
    {
      id: 'expense_total',
      label: 'Expenses',
      icon: Receipt,
      amount: props.expense,
      caption: '',
    },
  ];
  const inv = props.invoices || {};
  if (inv.sales) {
    out.push({
      id: 'sales_invoices',
      label: 'Sales Invoices',
      icon: FileText,
      amount: inv.sales.amount,
      caption: invoiceCaption(inv.sales),
    });
  }
  if (inv.purchase) {
    out.push({
      id: 'purchase_invoices',
      label: 'Purchase Invoices',
      icon: FileInput,
      amount: inv.purchase.amount,
      caption: invoiceCaption(inv.purchase),
    });
  }
  return out;
});
</script>

<template>
  <!-- Two-up on a phone, not one. A tile is one label and one number; stacked
       one per row, seven of them pushed every chart below the fold. -->
  <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 sm:gap-3">
    <BalanceTile
      v-for="t in BALANCE_TILES"
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

    <BalanceTile
      v-for="t in kpiTiles"
      :key="t.id"
      :tile-id="t.id"
      :label="t.label"
      :icon="t.icon"
      :amount="t.amount"
      :caption="t.caption"
      :currency="currency"
      :loading="!data"
    />
  </div>
</template>
