<script setup>
// f012 c004 — Income vs Expense trend.
//
// This component started life as the ApexCharts donut, was ported to ECharts in
// c001, and c004 collapses that port into the trend chart: two totals in a ring
// said nothing the KPI tiles (c003) do not now say better, while the shape of
// the period — which months earned, which months bled — was invisible.
//
// Income is drawn above the axis, expense below, on one stack so they meet at
// zero, with net as a line. Reading it is then a single question: is the line
// above the axis.
//
// It deliberately shows NO period total in its header. `series.totals` NETS
// reversing postings inside a bucket where the `income_total` / `expense_total`
// scalars behind the KPI tiles clamp each GL row at zero, so the two can differ
// legitimately. Putting one of them next to the other on the same screen would
// present a reconciliation problem as a contradiction. The footnote below names
// the difference instead, when there is one.
import { computed } from 'vue';
import CsChart from '@/components/shared/CsChart.vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';
import {
  SEMANTIC, CHROME, alpha, alphaToken, accent,
  moneyAxis, categoryAxis, moneyFormatters, tooltipRow, tooltipTitle,
} from '@/charts/theme';

const props = defineProps({
  // `dashboard_summary.series` — {granularity, buckets, income[], expense[], totals}
  series: { type: [Object, null], default: null },
  // The scalars behind the KPI tiles, for the reconciliation footnote only.
  income: { type: [Number, null], default: 0 },
  expense: { type: [Number, null], default: 0 },
  currency: { type: String, default: 'PKR' },
});

const buckets = computed(() => props.series?.buckets || []);
const incomeValues = computed(() => props.series?.income || []);
const expenseValues = computed(() => props.series?.expense || []);
const isDaily = computed(() => props.series?.granularity === 'daily');

const hasData = computed(() =>
  buckets.value.length > 0 &&
  [...incomeValues.value, ...expenseValues.value].some((v) => Math.abs(v || 0) > 0.005),
);

const netValues = computed(() =>
  buckets.value.map((_b, i) => (incomeValues.value[i] || 0) - (expenseValues.value[i] || 0)),
);

const chartedIncome = computed(() => props.series?.totals?.income ?? 0);
const chartedExpense = computed(() => props.series?.totals?.expense ?? 0);

/**
 * The scalars clamp each GL row at zero; the series nets. They diverge exactly
 * when an income or expense account carries a reversing posting inside the
 * period, and that divergence is worth saying out loud — a chart that quietly
 * adds up to a different number than the tile above it reads as a bug.
 */
const reconciliation = computed(() => {
  const diffs = [];
  if (Math.abs(chartedIncome.value - (props.income || 0)) > 0.01) {
    diffs.push({ label: 'income', charted: chartedIncome.value, booked: props.income || 0 });
  }
  if (Math.abs(chartedExpense.value - (props.expense || 0)) > 0.01) {
    diffs.push({ label: 'expense', charted: chartedExpense.value, booked: props.expense || 0 });
  }
  return diffs;
});

/** ISO dates are unreadable stacked on a daily axis; months already read fine. */
function axisLabel(bucket) {
  if (!isDaily.value) return bucket.label;
  const d = new Date(`${bucket.key}T00:00:00`);
  return Number.isNaN(d.getTime())
    ? bucket.label
    : d.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

const option = computed(() => {
  const { money, compact } = moneyFormatters(props.currency);
  const rows = buckets.value;

  return {
    grid: { top: 16, right: 12, bottom: 24, left: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: alphaToken('--cs-accent', 0.07) } },
      formatter: (params) => {
        if (!params?.length) return '';
        const i = params[0].dataIndex;
        const b = rows[i] || {};
        const inc = incomeValues.value[i] || 0;
        const exp = expenseValues.value[i] || 0;
        return (
          tooltipTitle(b.label || b.key || '') +
          tooltipRow(dot(SEMANTIC.income), 'Income', money(inc)) +
          tooltipRow(dot(SEMANTIC.expense), 'Expense', money(exp)) +
          `<div style="height:1px;background:${CHROME.border};margin:6px 0"></div>` +
          tooltipRow(dot(accent().base), 'Net', money(inc - exp))
        );
      },
    },
    legend: {
      show: true,
      bottom: 0,
      itemWidth: 8,
      itemHeight: 8,
      icon: 'circle',
      textStyle: { color: CHROME.textMuted, fontSize: 11 },
      data: ['Income', 'Expense', 'Net'],
    },
    xAxis: categoryAxis(rows.map(axisLabel), {
      axisLabel: {
        color: CHROME.axis,
        fontSize: 10,
        // A daily period can run to 92 buckets; let ECharts thin the labels
        // rather than rotating them into an unreadable comb.
        hideOverlap: true,
      },
    }),
    // Expense is plotted below the axis, so the axis formatter must not show a
    // minus on it — the colour and the side already say which is which.
    yAxis: moneyAxis(props.currency, {
      axisLabel: {
        color: CHROME.axis,
        fontSize: 10,
        formatter: (v) => compact(Math.abs(v)),
      },
    }),
    series: [
      {
        name: 'Income',
        type: 'bar',
        stack: 'flow',
        barMaxWidth: 28,
        itemStyle: { color: SEMANTIC.income, borderRadius: [3, 3, 0, 0] },
        data: incomeValues.value.map((v) => v || 0),
      },
      {
        name: 'Expense',
        type: 'bar',
        stack: 'flow',
        barMaxWidth: 28,
        itemStyle: { color: SEMANTIC.expense, borderRadius: [0, 0, 3, 3] },
        // Negated for placement only; every label and tooltip reports the
        // positive figure the ledger actually holds.
        data: expenseValues.value.map((v) => -(v || 0)),
      },
      {
        name: 'Net',
        type: 'line',
        smooth: false,
        symbol: 'circle',
        symbolSize: rows.length > 40 ? 0 : 5,
        lineStyle: { width: 2, color: accent().base },
        itemStyle: { color: accent().base },
        areaStyle: { color: alpha(accent().base, 0.06) },
        z: 3,
        data: netValues.value,
      },
    ],
  };
});

function dot(color) {
  return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px"></span>`;
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-4">
    <header class="mb-3">
      <h3 class="text-sm font-semibold text-gray-900">Income vs Expense</h3>
      <p class="text-xs text-gray-500">
        {{ isDaily ? 'Daily' : 'Monthly' }} — expense below the axis, net as the line
      </p>
    </header>

    <CsChart
      :option="option"
      :has-data="hasData"
      :height="260"
      aria-label="Income and expense per period with net line"
      empty-text="No income or expense posted this period."
    />

    <p
      v-for="d in reconciliation"
      :key="d.label"
      class="mt-2 text-[11px] leading-snug text-gray-500"
    >
      Charted {{ d.label }}
      <AmountDisplay :amount="d.charted" :currency="currency" class="text-gray-700" />
      against
      <AmountDisplay :amount="d.booked" :currency="currency" class="text-gray-700" />
      booked — the bars net reversing postings within a period, the tile above counts
      each posting as it stands.
    </p>
  </div>
</template>
