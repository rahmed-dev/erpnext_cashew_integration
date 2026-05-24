<script setup>
import { computed } from 'vue';

const props = defineProps({
  amount: { type: [Number, String], default: null },
  currency: { type: String, default: 'PKR' },
  signed: { type: Boolean, default: false },
  signSource: { type: [Number, String], default: null },
  compact: { type: Boolean, default: false },
  tabular: { type: Boolean, default: true },
  big: { type: Boolean, default: false },
});

const LOCALES = { PKR: 'en-PK', INR: 'en-IN', USD: 'en-US', EUR: 'en-DE', GBP: 'en-GB' };
const PREFIX = { PKR: 'Rs ', INR: '₹ ', USD: '$', EUR: '€', GBP: '£' };

function numeric() {
  if (props.amount === null || props.amount === undefined || props.amount === '') return null;
  const n = typeof props.amount === 'number' ? props.amount : parseFloat(props.amount);
  return Number.isFinite(n) ? n : null;
}

function formatCompact(value, locale) {
  const abs = Math.abs(value);
  if (props.currency === 'PKR' || props.currency === 'INR') {
    if (abs >= 1e7) return `${(value / 1e7).toFixed(1)}Cr`;
    if (abs >= 1e5) return `${(value / 1e5).toFixed(1)}L`;
    if (abs >= 1e3) return `${(value / 1e3).toFixed(0)}K`;
    return new Intl.NumberFormat(locale).format(value);
  }
  return new Intl.NumberFormat(locale, { notation: 'compact', maximumFractionDigits: 1 }).format(value);
}

const formatted = computed(() => {
  const n = numeric();
  if (n === null) return null;
  const locale = LOCALES[props.currency] || 'en-US';
  const prefix = PREFIX[props.currency] || '';
  const abs = Math.abs(n);
  const body = props.compact
    ? formatCompact(abs, locale)
    : new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(abs);
  return `${prefix}${body}`;
});

const direction = computed(() => {
  if (!props.signed) return null;
  const src = props.signSource !== null && props.signSource !== undefined ? props.signSource : numeric();
  if (typeof src === 'number') return src < 0 ? 'down' : src > 0 ? 'up' : 'zero';
  if (typeof src === 'string') {
    if (src === 'Income') return 'up';
    if (src === 'Expense') return 'down';
  }
  return 'zero';
});
</script>

<template>
  <span
    :class="[
      tabular ? 'tabular-nums' : '',
      big ? 'text-[26px] font-semibold tracking-[-0.02em]' : '',
      direction === 'up' ? 'text-green-700' : direction === 'down' ? 'text-red-700' : '',
    ]"
  >
    <template v-if="formatted === null">
      <span class="text-gray-400">—</span>
    </template>
    <template v-else>
      <template v-if="signed && direction === 'up'">+</template>
      <template v-else-if="signed && direction === 'down'">−</template>
      {{ formatted }}
    </template>
  </span>
</template>
