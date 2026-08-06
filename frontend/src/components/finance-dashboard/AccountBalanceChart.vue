<script setup>
// f012 c010 — one band per asset account over the period.
//
// UNGATED per Decision 7. On this ledger Petty Cash sits deep in negative
// territory and, if the optional backfill has run, an Investment account sits
// near -447,850. Those are what the source says.
//
// THE STACKING DECISION. A stacked area only means anything when every band is
// positive: the top edge is then the total and each band's thickness is that
// account's share of it. Mix a large negative in and neither statement holds —
// ECharts stacks negatives onto their own baseline, so the top edge stops being
// the total and a reader measuring band thickness is measuring nothing. So the
// chart switches: all-positive draws stacked areas, and any account going
// negative in the window drops the whole chart to plain unstacked lines, with
// the header saying which mode is in force and why. Silently keeping the stack
// would be the failure that matters here — it looks correct and isn't.
import { computed } from 'vue';
import CsChart from '@/components/shared/CsChart.vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';
import {
  RAMP, CHROME, alpha,
  moneyAxis, categoryAxis, moneyFormatters, tooltipRow, tooltipTitle,
} from '@/charts/theme';

const props = defineProps({
  // `dashboard_summary.series` — needs `buckets` and `balances`.
  series: { type: [Object, null], default: null },
  currency: { type: String, default: 'PKR' },
});

const buckets = computed(() => props.series?.buckets || []);
const accounts = computed(() => props.series?.balances || []);
const isDaily = computed(() => props.series?.granularity === 'daily');

const hasData = computed(() =>
  buckets.value.length > 0 &&
  accounts.value.some((a) => (a.values || []).some((v) => Math.abs(v || 0) > 0.005)),
);

/** Any negative anywhere in the window disqualifies the stack — see the note above. */
const hasNegative = computed(() =>
  accounts.value.some((a) => (a.values || []).some((v) => (v || 0) < -0.005)),
);
const stacked = computed(() => !hasNegative.value);

// The accounts the server folded into the "(Other)" band. The tooltip is
// per-bucket and the fold only carries closing balances, so they are named
// underneath rather than nested in it — an unnamed band in a stack of ten is
// the one the reader most wants identified.
const folded = computed(
  () => accounts.value.find((a) => (a.members || []).length)?.members || [],
);

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
  const list = accounts.value;
  const isStacked = stacked.value;

  return {
    grid: { top: 16, right: 12, bottom: 28, left: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line', lineStyle: { color: CHROME.border } },
      formatter: (params) => {
        if (!params?.length) return '';
        const i = params[0].dataIndex;
        const b = rows[i] || {};
        // Ordered by the value at this bucket, not by series order: on a chart
        // with ten bands the reader is looking for who is largest HERE.
        const lines = list
          .map((a, idx) => ({ label: a.label, value: a.values?.[i] || 0, idx }))
          .sort((x, y) => Math.abs(y.value) - Math.abs(x.value))
          .map((x) => tooltipRow(dot(RAMP[x.idx % RAMP.length]), x.label, money(x.value)));
        const total = list.reduce((sum, a) => sum + (a.values?.[i] || 0), 0);
        return (
          tooltipTitle(b.label || b.key || '') +
          lines.join('') +
          `<div style="height:1px;background:${CHROME.border};margin:6px 0"></div>` +
          tooltipRow(dot(CHROME.textMuted), 'Total', money(total))
        );
      },
    },
    legend: {
      show: true,
      bottom: 0,
      type: 'scroll',
      itemWidth: 8,
      itemHeight: 8,
      icon: 'circle',
      textStyle: { color: CHROME.textMuted, fontSize: 11 },
      data: list.map((a) => a.label),
    },
    xAxis: categoryAxis(rows.map(axisLabel), {
      boundaryGap: false,
      axisLabel: { color: CHROME.axis, fontSize: 10, hideOverlap: true },
    }),
    // `scale: true` only in line mode: a stack read against a floating baseline
    // would misstate every band's share, but a line chart of accounts that never
    // approach zero needs the room.
    yAxis: moneyAxis(props.currency, {
      scale: !isStacked,
      axisLabel: { color: CHROME.axis, fontSize: 10, formatter: (v) => compact(v) },
    }),
    series: list.map((a, idx) => {
      const color = RAMP[idx % RAMP.length];
      return {
        name: a.label,
        type: 'line',
        smooth: false,
        symbol: 'circle',
        symbolSize: rows.length > 40 ? 0 : 4,
        lineStyle: { width: isStacked ? 1 : 2, color },
        itemStyle: { color },
        // Translucency MUST go through alpha(); zrender cannot parse a CSS
        // color-mix() and renders it black without warning.
        ...(isStacked
          ? { stack: 'balance', areaStyle: { color: alpha(color, 0.5) } }
          : {}),
        data: (a.values || []).map((v) => v || 0),
      };
    }),
  };
});

function dot(color) {
  return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px"></span>`;
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-4">
    <header class="mb-3">
      <h3 class="text-sm font-semibold text-gray-900">Account balances</h3>
      <p class="text-xs text-gray-500">
        <template v-if="stacked">
          {{ isDaily ? 'Daily' : 'Monthly' }} closing balance per account, stacked
        </template>
        <template v-else>
          {{ isDaily ? 'Daily' : 'Monthly' }} closing balance per account — shown as
          separate lines, because an account below zero makes a stack unreadable
        </template>
      </p>
    </header>

    <CsChart
      :option="option"
      :has-data="hasData"
      :height="280"
      aria-label="Closing balance per account over the period"
      empty-text="No account carried a balance in this period."
    />

    <p v-if="folded.length" class="mt-2 text-[11px] leading-snug text-gray-500">
      (Other) is
      <span v-for="(m, i) in folded" :key="m.label">
        <span class="text-gray-700">{{ m.label }}</span>
        (<AmountDisplay :amount="m.closing" :currency="currency" signed />){{ i < folded.length - 1 ? ', ' : '' }}
      </span>, closing.
    </p>
  </div>
</template>
