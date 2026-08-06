<script setup>
// f012 c006 — expense breakdown as a treemap.
//
// D3.b: treemap, NOT sunburst. f011's scan found `sub_category_fk` unused on
// every row in both exports, so the category dimension is flat today and a
// sunburst would degenerate into the donut the dashboard already carries. The
// data contract below is nevertheless hierarchical — every node has a `children`
// array, empty today — so moving to a sunburst later is a chart-type change in
// this one component rather than a reshape of what the server sends.
//
// AREA CANNOT SHOW A NEGATIVE. A treemap tile's meaning is its area, and there
// is no area smaller than none. `expense_by_category` reports the NET movement
// per category, so a category whose refunds outweigh its spending in the period
// comes through negative and simply cannot be drawn here. It is excluded from
// the tiles and named underneath with its figure, because a category that
// silently vanishes from a breakdown is the reader's problem, not ours.
import { computed } from 'vue';
import CsChart from '@/components/shared/CsChart.vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';
import {
  RAMP, CHROME,
  moneyFormatters, tooltipRow, tooltipTitle,
} from '@/charts/theme';

const props = defineProps({
  // `dashboard_summary.series` — needs `expense_by_category`.
  series: { type: [Object, null], default: null },
  currency: { type: String, default: 'PKR' },
});

const rows = computed(() => props.series?.expense_by_category || []);

/**
 * The hierarchy-ready node contract. Every row becomes one node with an empty
 * `children` array; when Cashew sub-categories are eventually imported this
 * function is the only thing that changes.
 */
const nodes = computed(() =>
  rows.value
    .map((r) => ({ name: r.label, value: r.total || 0, children: [] }))
    .filter((n) => n.value > 0.005)
    .sort((a, b) => b.value - a.value),
);

/** Categories that netted to zero or below — drawable nowhere, listed instead. */
const excluded = computed(() =>
  rows.value
    .filter((r) => (r.total || 0) <= 0.005)
    .map((r) => ({ label: r.label, total: r.total || 0 }))
    .sort((a, b) => a.total - b.total),
);

const total = computed(() => nodes.value.reduce((sum, n) => sum + n.value, 0));
const hasData = computed(() => nodes.value.length > 0 && total.value > 0.005);

const option = computed(() => {
  const { money, compact } = moneyFormatters(props.currency);
  const sum = total.value || 1;

  return {
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        const share = ((p.value / sum) * 100).toFixed(1);
        return (
          tooltipTitle(p.name) +
          tooltipRow(dot(p.color), 'Spent', money(p.value)) +
          tooltipRow(dot(CHROME.textFaint), 'Share', `${share}%`)
        );
      },
    },
    series: [
      {
        type: 'treemap',
        // A flat breakdown is not something to navigate: drilling, zooming and
        // the breadcrumb bar all imply a depth this data does not have.
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        animationDuration: 300,
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        width: '100%',
        height: '100%',
        // The gap is the card's own surface colour, so tiles read as separated
        // rather than outlined.
        itemStyle: { borderColor: CHROME.surface, borderWidth: 0, gapWidth: 2 },
        label: {
          show: true,
          color: '#ffffff',
          fontSize: 11,
          lineHeight: 15,
          overflow: 'truncate',
          formatter: (p) => `${p.name}\n${compact(p.value)}`,
        },
        // Small tiles get their label suppressed by ECharts rather than
        // overflowing; below this the text would be unreadable anyway.
        labelLayout: { hideOverlap: true },
        data: nodes.value.map((n, i) => ({
          ...n,
          itemStyle: { color: RAMP[i % RAMP.length] },
        })),
      },
    ],
  };
});

function dot(color) {
  return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px"></span>`;
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-5">
    <header class="mb-3 flex items-start justify-between gap-4">
      <div>
        <h3 class="text-sm font-semibold text-gray-900">Where the money went</h3>
        <p class="text-xs text-gray-500">
          Expense by category, tile area proportional to the amount
        </p>
      </div>
      <div v-if="hasData" class="text-right shrink-0">
        <AmountDisplay :amount="total" :currency="currency" class="text-base font-semibold" />
        <div class="text-xs text-gray-500 mt-0.5">{{ nodes.length }} categories</div>
      </div>
    </header>

    <CsChart
      :option="option"
      :has-data="hasData"
      :height="300"
      aria-label="Expense by category, sized by amount"
      empty-text="No expense was posted in this period."
    />

    <!-- See the note at the top of this file: these cannot be tiles, so they
         are stated in words rather than dropped. -->
    <p v-if="excluded.length" class="mt-3 text-[11px] leading-snug text-gray-500">
      Not shown, because the period nets to zero or a refund:
      <span v-for="(e, i) in excluded" :key="e.label">
        <span class="text-gray-700">{{ e.label }}</span>
        (<AmountDisplay :amount="e.total" :currency="currency" signed />){{ i < excluded.length - 1 ? ', ' : '' }}
      </span>
    </p>
  </div>
</template>
