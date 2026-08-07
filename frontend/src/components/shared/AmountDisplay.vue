<script setup>
import { computed } from 'vue';
import { formatCompactNumber, formatNumber, prefixFor } from '@/utils/money';

const props = defineProps({
  amount: { type: [Number, String], default: null },
  currency: { type: String, default: 'PKR' },
  signed: { type: Boolean, default: false },
  signSource: { type: [Number, String], default: null },
  compact: { type: Boolean, default: false },
  tabular: { type: Boolean, default: true },
  big: { type: Boolean, default: false },
});

// `big` is the balance-tile figure and nothing else. It scales with the
// breakpoint because the tiles sit two-up on a phone, where a fixed desktop
// size for "Rs 1,885,076.42" overflows its own card.
//
// These are deliberately modest for a headline number. The tiles are a strip
// the reader scans past on the way to the charts, not the point of the page,
// and at the earlier 26px seven of them owned the whole first screen. A figure
// only has to be legible to be read; it does not have to be large.
// The step DOWN at xl is not a mistake: that is where the tile strip goes to
// seven columns, so each tile is narrower there than at lg despite the wider
// page, and a seven-digit figure has to keep fitting on one line.
const BIG_CLASS =
  'text-[15px] sm:text-[16px] lg:text-[18px] xl:text-[16px] font-semibold tracking-[-0.02em] whitespace-nowrap';

function numeric() {
  if (props.amount === null || props.amount === undefined || props.amount === '') return null;
  const n = typeof props.amount === 'number' ? props.amount : parseFloat(props.amount);
  return Number.isFinite(n) ? n : null;
}

const formatted = computed(() => {
  const n = numeric();
  if (n === null) return null;
  const abs = Math.abs(n);
  const body = props.compact
    ? formatCompactNumber(abs, props.currency)
    : formatNumber(abs, props.currency, 2);
  return `${prefixFor(props.currency)}${body}`;
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
      big ? BIG_CLASS : '',
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
