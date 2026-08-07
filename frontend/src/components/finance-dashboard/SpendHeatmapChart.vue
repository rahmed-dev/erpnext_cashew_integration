<script setup>
// f012 c007 — calendar heatmap of daily spend density.
//
// Reads c002's `daily_spend` block, which is ALWAYS daily whatever the period
// length: a calendar is a day grid by nature, so it never follows the series'
// daily/monthly granularity switch.
//
// THE SCALE IS CAPPED AT A PERCENTILE, NOT THE MAXIMUM. Spending is long-tailed
// — one rent day or one equipment purchase is an order of magnitude above a
// normal day — and anchoring the colour ramp at the true maximum pushes every
// ordinary day into the palest band, leaving a grid that says nothing except
// "one day was big". The ramp therefore tops out near the 94th percentile of
// spending days and the days above it share the darkest colour, which is stated
// under the chart rather than left for the reader to discover.
//
// Days that net to zero are drawn as empty cells rather than the lightest
// colour, so "nothing happened" is visually distinct from "a little happened".
// A day whose refunds outweigh its spending is uncolourable on a scale that
// starts at zero, so it is left empty too and counted in words underneath.
import { computed } from 'vue';
import CsChart from '@/components/shared/CsChart.vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';
import {
  CHROME, accent, alpha,
  moneyFormatters, tooltipRow, tooltipTitle,
} from '@/charts/theme';

const props = defineProps({
  // `dashboard_summary.daily_spend` — [{ date, amount }], dense.
  days: { type: Array, default: () => [] },
  currency: { type: String, default: 'PKR' },
  // Only to say so when the dashboard is drawn at a wider width. This chart does
  // NOT follow the granularity control — a calendar with a cell per month is not
  // a calendar — and a reader who has just set the dashboard to Monthly needs
  // that stated rather than left to look like the control was ignored.
  series: { type: [Object, null], default: null },
});

const dashboardIsDaily = computed(
  () => !props.series || props.series.granularity === 'daily',
);

const CELL = 14;
/** Column of day-of-week labels plus the month labels above each calendar. */
const CALENDAR_TOP = 22;
const CALENDAR_BLOCK = CELL * 7 + 48;

const rows = computed(() => (props.days || []).filter((d) => d && d.date));

/** One calendar per year in view, each clipped to the period it actually covers. */
const years = computed(() => {
  const grouped = new Map();
  for (const row of rows.value) {
    const year = String(row.date).slice(0, 4);
    if (!grouped.has(year)) grouped.set(year, []);
    grouped.get(year).push(row);
  }
  return [...grouped.entries()]
    .sort((a, b) => (a[0] < b[0] ? -1 : 1))
    .map(([year, list]) => ({
      year,
      range: [list[0].date, list[list.length - 1].date],
      list,
    }));
});

const spendDays = computed(() =>
  rows.value.map((d) => d.amount || 0).filter((v) => v > 0.005),
);

const hasData = computed(() => spendDays.value.length > 0);

/**
 * The 94th percentile of days that carried spending. Zero days are excluded
 * from the ranking — on a period with weekends and gaps they are most of the
 * grid, and including them would drag the cap down to near nothing.
 */
const cap = computed(() => {
  const sorted = [...spendDays.value].sort((a, b) => a - b);
  if (!sorted.length) return 1;
  const idx = Math.floor(0.94 * (sorted.length - 1));
  return sorted[idx] || sorted[sorted.length - 1] || 1;
});

const peak = computed(() => Math.max(0, ...spendDays.value));
const cappedCount = computed(() => spendDays.value.filter((v) => v > cap.value).length);
const refunds = computed(() => rows.value.filter((d) => (d.amount || 0) < -0.005));
const refundTotal = computed(() =>
  refunds.value.reduce((sum, d) => sum + Math.abs(d.amount || 0), 0),
);

const chartHeight = computed(() => CALENDAR_TOP + years.value.length * CALENDAR_BLOCK + 30);

const option = computed(() => {
  const { money, compact } = moneyFormatters(props.currency);
  const shades = accent();

  return {
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        const [key, value] = p.value || [];
        const amount = Number(value) || 0;
        const label = new Date(`${key}T00:00:00`).toLocaleDateString(undefined, {
          weekday: 'short', day: 'numeric', month: 'short', year: 'numeric',
        });
        return tooltipTitle(label) + tooltipRow(dot(shades.base), 'Spent', money(amount));
      },
    },
    visualMap: {
      type: 'continuous',
      min: 0,
      max: cap.value,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemWidth: 10,
      itemHeight: 90,
      textStyle: { color: CHROME.axis, fontSize: 10 },
      text: [`${compact(cap.value)}+`, '0'],
      inRange: {
        // Single-series chart: the accent governs, per Decision 4. Built with
        // alpha() — zrender cannot parse a CSS color-mix() and would render the
        // whole grid black without warning.
        color: [alpha(shades.base, 0.1), shades.base, shades.dark],
      },
    },
    calendar: years.value.map((y, i) => ({
      top: CALENDAR_TOP + i * CALENDAR_BLOCK,
      left: 34,
      right: 12,
      // Width is 'auto' (c011): on a phone a fixed 14px cell across six months
      // runs off the canvas and the last weeks simply vanish. A non-square cell
      // is a cosmetic loss; a missing week is a factual one, so the grid gives
      // up squareness to keep every day on screen. Height stays fixed so the
      // seven-row week never collapses.
      cellSize: ['auto', CELL],
      range: y.range,
      splitLine: { show: false },
      itemStyle: { color: CHROME.surface, borderColor: CHROME.grid, borderWidth: 1 },
      yearLabel: { show: years.value.length > 1, color: CHROME.textFaint, fontSize: 11 },
      monthLabel: { color: CHROME.axis, fontSize: 10 },
      dayLabel: { color: CHROME.axis, fontSize: 10, firstDay: 1 },
    })),
    series: years.value.map((y, i) => ({
      type: 'heatmap',
      coordinateSystem: 'calendar',
      calendarIndex: i,
      // '-' is ECharts' no-data marker: the cell keeps the empty background
      // instead of taking the lightest colour of the ramp.
      data: y.list.map((d) =>
        (d.amount || 0) > 0.005 ? [d.date, d.amount] : [d.date, '-'],
      ),
    })),
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
        <h3 class="text-sm font-semibold text-gray-900">Spending calendar</h3>
        <p class="text-xs text-gray-500">
          One cell per day, darker means more spent<template v-if="!dashboardIsDaily"> — always
          daily, whatever width the rest of the dashboard is set to</template>
        </p>
      </div>
      <div v-if="hasData" class="text-right shrink-0 text-xs text-gray-500">
        {{ spendDays.length }} days with spending
      </div>
    </header>

    <CsChart
      :option="option"
      :has-data="hasData"
      :height="chartHeight"
      aria-label="Daily spending density across the period"
      empty-text="No expense was posted on any day in this period."
    />

    <p v-if="hasData" class="mt-2 text-[11px] leading-snug text-gray-500">
      The colour scale stops near the 94th percentile so ordinary days stay
      readable.
      <template v-if="cappedCount">
        {{ cappedCount }} {{ cappedCount === 1 ? 'day is' : 'days are' }} above it,
        peaking at <AmountDisplay :amount="peak" :currency="currency" />, and all
        share the darkest shade.
      </template>
      <template v-if="refunds.length">
        {{ refunds.length }} {{ refunds.length === 1 ? 'day' : 'days' }} netted to a
        refund of <AmountDisplay :amount="refundTotal" :currency="currency" /> in total
        and {{ refunds.length === 1 ? 'is' : 'are' }} left uncoloured, since the scale
        starts at zero.
      </template>
    </p>
  </div>
</template>
