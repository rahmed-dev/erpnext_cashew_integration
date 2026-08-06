<script setup>
// f012 c005 — Net worth over the period.
//
// UNGATED per Decision 7: an earlier plan blocked this chart on posting opening
// balances first, and there are none to post. The curve on this ledger runs
// deeply negative because the source data does — cash was spent that was never
// recorded as arriving. That is a true statement about the books and the chart
// says it plainly: the zero line is drawn, the area below it is tinted in the
// expense hue, and the y-axis is left to ECharts so a large negative simply
// gets room rather than being clipped or floored at zero.
//
// It is a line, not a stack. `series.net_worth` already nets assets against
// liabilities on the server, and the tooltip breaks the figure back apart.
import { computed } from 'vue';
import CsChart from '@/components/shared/CsChart.vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';
import {
  SEMANTIC, CHROME, alpha, accent,
  moneyAxis, categoryAxis, moneyFormatters, tooltipRow, tooltipTitle,
} from '@/charts/theme';

const props = defineProps({
  // `dashboard_summary.series` — needs `buckets` and `net_worth`.
  series: { type: [Object, null], default: null },
  currency: { type: String, default: 'PKR' },
});

const buckets = computed(() => props.series?.buckets || []);
const block = computed(() => props.series?.net_worth || null);
const values = computed(() => block.value?.values || []);
const isDaily = computed(() => props.series?.granularity === 'daily');

// A net worth of exactly zero across every bucket means no balance-sheet account
// has ever been posted to — that is the empty state. A negative curve is DATA,
// not emptiness, so `some(v => v !== 0)` is the test rather than `some(v > 0)`.
const hasData = computed(() =>
  buckets.value.length > 0 && values.value.some((v) => Math.abs(v || 0) > 0.005),
);

const opening = computed(() => block.value?.opening ?? 0);
const closing = computed(() => block.value?.closing ?? 0);
const change = computed(() => closing.value - opening.value);
const goesNegative = computed(() => values.value.some((v) => (v || 0) < -0.005));

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
  const assets = block.value?.assets || [];
  const liabilities = block.value?.liabilities || [];
  const hasLiabilities = !!block.value?.has_liabilities;

  return {
    grid: { top: 16, right: 12, bottom: 8, left: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: CHROME.border } },
      formatter: (params) => {
        if (!params?.length) return '';
        const i = params[0].dataIndex;
        const b = rows[i] || {};
        const net = values.value[i] || 0;
        const rowsOut = [tooltipTitle(b.label || b.key || '')];
        rowsOut.push(tooltipRow(dot(CHROME.textMuted), 'Assets', money(assets[i] || 0)));
        // The liabilities row is suppressed when the ledger has none at all
        // rather than printed as a zero: a standing zero invites the reader to
        // wonder which debts were missed.
        if (hasLiabilities) {
          rowsOut.push(tooltipRow(dot(SEMANTIC.expense), 'Owed', money(liabilities[i] || 0)));
        }
        rowsOut.push(`<div style="height:1px;background:${CHROME.border};margin:6px 0"></div>`);
        rowsOut.push(tooltipRow(dot(accent().base), 'Net worth', money(net)));
        return rowsOut.join('');
      },
    },
    xAxis: categoryAxis(rows.map(axisLabel), {
      boundaryGap: false,
      axisLabel: { color: CHROME.axis, fontSize: 10, hideOverlap: true },
    }),
    // `scale: true` is deliberate. Without it ECharts anchors a value axis at
    // zero, which on a curve that never rises above a large negative squashes
    // the whole shape into the top edge.
    yAxis: moneyAxis(props.currency, {
      scale: true,
      axisLabel: { color: CHROME.axis, fontSize: 10, formatter: (v) => compact(v) },
    }),
    series: [
      {
        name: 'Net worth',
        type: 'line',
        smooth: false,
        symbol: 'circle',
        symbolSize: rows.length > 40 ? 0 : 5,
        lineStyle: { width: 2, color: accent().base },
        itemStyle: { color: accent().base },
        // The fill is measured from zero, not from the bottom of the plot, so
        // the tinted band under a negative curve is the shortfall itself.
        areaStyle: { origin: 0, color: alpha(accent().base, 0.08) },
        data: values.value.map((v) => v || 0),
        markLine: {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: CHROME.axis, type: 'dashed', width: 1 },
          data: [{ yAxis: 0 }],
        },
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
    <header class="mb-3 flex items-start justify-between gap-4">
      <div>
        <h3 class="text-sm font-semibold text-gray-900">Net worth</h3>
        <p class="text-xs text-gray-500">
          {{ isDaily ? 'Daily' : 'Monthly' }} closing balance, assets less liabilities
        </p>
      </div>
      <div v-if="hasData" class="text-right shrink-0">
        <AmountDisplay :amount="closing" :currency="currency" class="text-base font-semibold" />
        <div class="text-xs text-gray-500 mt-0.5">
          <AmountDisplay :amount="change" :currency="currency" signed />
          this period
        </div>
      </div>
    </header>

    <CsChart
      :option="option"
      :has-data="hasData"
      :height="260"
      aria-label="Net worth at the close of each period"
      empty-text="No balance-sheet account has been posted to in this period."
    />

    <!--
      Stated, not hidden. The negative is a property of the imported ledger —
      spending recorded without the matching funding — and a reader who sees it
      without explanation will assume the chart is broken.
    -->
    <p v-if="goesNegative" class="mt-2 text-[11px] leading-snug text-gray-500">
      The curve runs below zero because the imported ledger records the spending
      without the opening balances or funding that preceded it. It is what the
      books say, not a charting error.
    </p>
  </div>
</template>
