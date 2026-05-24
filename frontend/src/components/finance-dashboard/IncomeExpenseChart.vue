<script setup>
import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';

const props = defineProps({
  income: { type: [Number, null], default: 0 },
  expense: { type: [Number, null], default: 0 },
  incomeBy: { type: Array, default: () => [] },
  expenseBy: { type: Array, default: () => [] },
  currency: { type: String, default: 'PKR' },
  period: { type: Object, default: () => ({}) },
});

const net = computed(() => (props.income || 0) - (props.expense || 0));

const series = computed(() => [
  Math.max(props.income || 0, 0),
  Math.max(props.expense || 0, 0),
]);

const accent = ref({ income: '#4f46e5', expense: '#334155' });

function readAccents() {
  if (typeof window === 'undefined') return;
  const cs = getComputedStyle(document.documentElement);
  const primary = cs.getPropertyValue('--cs-accent').trim() || '#4f46e5';
  accent.value = { income: primary, expense: '#334155' };
}

const themeObserver = ref(null);
onMounted(() => {
  readAccents();
  themeObserver.value = new MutationObserver(readAccents);
  themeObserver.value.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['style'],
  });
});
onBeforeUnmount(() => {
  themeObserver.value?.disconnect();
});

// Hover state — driven by ApexCharts dataPointMouseEnter / dataPointMouseLeave.
// null = nothing hovered, 0 = income slice, 1 = expense slice.
const hoverIdx = ref(null);
const cursor = ref({ x: 0, y: 0 });
const chartWrap = ref(null);

function onChartMove(e) {
  if (!chartWrap.value) return;
  const rect = chartWrap.value.getBoundingClientRect();
  cursor.value = { x: e.clientX - rect.left, y: e.clientY - rect.top };
}

// Floating tooltip placement: prefer right of cursor, flip left near right edge.
// Vertically clamp inside the wrapper.
const tooltipStyle = computed(() => {
  const PAD = 12;
  const W = 260;
  const wrap = chartWrap.value;
  const wrapW = wrap?.clientWidth || 400;
  const wrapH = wrap?.clientHeight || 280;
  let left = cursor.value.x + PAD;
  if (left + W > wrapW - 4) left = Math.max(4, cursor.value.x - W - PAD);
  // estimate panel height ~ 220, clamp y so it fits
  const H = 220;
  let top = cursor.value.y + PAD;
  if (top + H > wrapH - 4) top = Math.max(4, wrapH - H - 4);
  return { left: `${left}px`, top: `${top}px`, width: `${W}px` };
});

const chartOptions = computed(() => ({
  chart: {
    type: 'donut',
    fontFamily: 'inherit',
    toolbar: { show: false },
    animations: { enabled: true, speed: 350 },
    events: {
      dataPointMouseEnter: (_e, _ctx, cfg) => {
        if (cfg && typeof cfg.dataPointIndex === 'number') hoverIdx.value = cfg.dataPointIndex;
      },
      dataPointMouseLeave: () => {
        hoverIdx.value = null;
      },
    },
  },
  labels: ['Income', 'Expense'],
  colors: [accent.value.income, accent.value.expense],
  stroke: { width: 2, colors: ['#ffffff'] },
  legend: { show: false },
  dataLabels: { enabled: false },
  plotOptions: {
    pie: {
      donut: {
        size: '68%',
        labels: { show: false },
      },
    },
  },
  tooltip: { enabled: false },
  states: { hover: { filter: { type: 'lighten', value: 0.06 } } },
}));

const hasData = computed(() => (props.income || 0) + (props.expense || 0) > 0);
const isPositive = computed(() => net.value >= 0);

const hoverMeta = computed(() => {
  if (hoverIdx.value === 0) {
    return {
      label: 'Income',
      color: accent.value.income,
      total: props.income || 0,
      rows: (props.incomeBy || []).filter((r) => r.account !== '(Other)'),
    };
  }
  if (hoverIdx.value === 1) {
    return {
      label: 'Expense',
      color: accent.value.expense,
      total: props.expense || 0,
      rows: (props.expenseBy || []).filter((r) => r.account !== '(Other)'),
    };
  }
  return null;
});

const hoverRowsToShow = computed(() => {
  const meta = hoverMeta.value;
  if (!meta) return [];
  const top = meta.rows.slice(0, 5);
  const tail = meta.rows.slice(5);
  if (tail.length) {
    const sum = tail.reduce((s, x) => s + (x.amount || 0), 0);
    top.push({ account: `+ ${tail.length} more`, amount: sum, _tail: true });
  }
  return top;
});

function pct(amount, total) {
  if (!total) return 0;
  return Math.round((Math.abs(amount || 0) / total) * 100);
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-5">
    <header class="mb-3 flex items-start justify-between gap-3">
      <div>
        <h3 class="text-sm font-semibold text-gray-900">Income vs Expense</h3>
        <p class="text-xs text-gray-500">Hover a slice for top-account breakdown</p>
      </div>
      <div class="text-right">
        <div class="text-[10px] uppercase tracking-wide text-gray-500">Net</div>
        <div :class="['text-lg font-semibold tabular-nums', isPositive ? 'text-[var(--cs-accent-700)]' : 'text-gray-700']">
          <AmountDisplay :amount="net" :currency="currency" :signed="true" />
        </div>
      </div>
    </header>

    <div v-if="hasData" class="relative">
      <div
        ref="chartWrap"
        class="-mt-2 relative"
        @mousemove="onChartMove"
        @mouseleave="hoverIdx = null"
      >
        <apexchart
          type="donut"
          height="240"
          :options="chartOptions"
          :series="series"
        />

        <!-- Floating breakdown panel beside cursor -->
        <div
          v-if="hoverMeta"
          class="absolute z-20 rounded-md border border-gray-200 bg-white shadow-lg p-3 pointer-events-none"
          :style="tooltipStyle"
        >
          <div class="flex items-center justify-between gap-3 mb-2 pb-2 border-b border-gray-100">
            <span class="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-gray-700">
              <span class="w-2 h-2 rounded-full" :style="`background:${hoverMeta.color}`" />
              {{ hoverMeta.label }}
            </span>
            <span class="text-xs font-semibold tabular-nums text-gray-900">
              <AmountDisplay :amount="hoverMeta.total" :currency="currency" />
            </span>
          </div>
          <div class="text-[10px] uppercase tracking-wide text-gray-400 mb-1">Top accounts</div>
          <ul v-if="hoverRowsToShow.length" class="space-y-1">
            <li
              v-for="(r, i) in hoverRowsToShow"
              :key="i"
              class="flex items-center justify-between text-xs gap-2"
            >
              <span :class="['truncate min-w-0', r._tail ? 'text-gray-500 italic' : 'text-gray-700']">
                {{ r.account }}
              </span>
              <span class="shrink-0 inline-flex items-baseline gap-1.5 tabular-nums">
                <AmountDisplay :amount="r.amount" :currency="currency" class="text-gray-900" />
                <span class="text-[10px] text-gray-400">· {{ pct(r.amount, hoverMeta.total) }}%</span>
              </span>
            </li>
          </ul>
          <p v-else class="text-xs text-gray-400 italic">No accounts.</p>
        </div>
      </div>

      <!-- Always-on legend + totals below chart -->
      <div class="mt-3 grid grid-cols-2 gap-3 text-xs">
        <div class="flex flex-col items-start">
          <span class="inline-flex items-center gap-1.5 text-gray-600">
            <span class="w-2.5 h-2.5 rounded-full" :style="`background:${accent.income}`" />
            Income
          </span>
          <AmountDisplay :amount="income" :currency="currency" class="mt-0.5 font-medium text-gray-900" />
        </div>
        <div class="flex flex-col items-start">
          <span class="inline-flex items-center gap-1.5 text-gray-600">
            <span class="w-2.5 h-2.5 rounded-full" :style="`background:${accent.expense}`" />
            Expense
          </span>
          <AmountDisplay :amount="expense" :currency="currency" class="mt-0.5 font-medium text-gray-900" />
        </div>
      </div>
    </div>

    <div v-else class="py-10 text-center text-xs text-gray-400 italic">
      No income or expense posted this period.
    </div>
  </div>
</template>
