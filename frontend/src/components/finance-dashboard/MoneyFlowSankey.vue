<script setup>
// f012 c008 — money flow as a three-column sankey.
//
// Income accounts on the left, the accounts the money landed in in the middle,
// the categories it left through on the right. The server (dashboard_series
// .money_flow) does the voucher pairing, the layer classification and the
// top-N fold; this component draws what it is handed and does not reshape it.
//
// THE DIAGRAM IS A SUBSET OF THE LEDGER, AND SAYS SO. Only Income -> Account
// and Account -> Category links can be drawn: a transfer between two accounts
// would be a link inside a single column, and a loan or an opening-balance leg
// belongs to neither end of the story this chart tells. On a real ledger the
// excluded amount is not a rounding detail — on this one it is larger than the
// drawn flow — so it is reported underneath in figures rather than left as a
// silent gap between the chart and the tiles above it.
//
// A LINK IS NOT ALWAYS AN OBSERVATION. A two-legged voucher pins the source to
// the use exactly; a voucher with several funding legs and several uses does
// not, and the server splits it proportionally. The count of such vouchers is
// stated too, because a reader tracing one ribbon deserves to know whether the
// ledger actually recorded that pairing.
import { computed } from 'vue';
import CsChart from '@/components/shared/CsChart.vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';
import {
  SEMANTIC, CHROME, alpha, accent,
  moneyFormatters, tooltipRow, tooltipTitle,
} from '@/charts/theme';

const props = defineProps({
  // `dashboard_summary.money_flow` — { nodes, links, inflow, outflow, excluded, ... }.
  flow: { type: [Object, null], default: null },
  currency: { type: String, default: 'PKR' },
});

const nodes = computed(() => props.flow?.nodes || []);
const links = computed(() => props.flow?.links || []);
const excluded = computed(() => props.flow?.excluded || { transfers: 0, other: 0, total: 0 });
// The two columns are reported and shown separately, never added together: the
// same money is counted once as it arrives and again as it leaves, so a single
// "total flow" figure would be roughly double anything in the ledger. What
// separates them — earned minus spent — is the part that stayed in the accounts.
const inflow = computed(() => props.flow?.inflow || 0);
const outflow = computed(() => props.flow?.outflow || 0);
const allocated = computed(() => props.flow?.allocated_vouchers || 0);

const hasData = computed(
  () => links.value.length > 0 && (inflow.value + outflow.value) > 0.005,
);

/** One colour per column. Income and expense keep their fixed semantic hues so
 *  the sankey agrees with the trend chart; the middle column is the accent,
 *  which is where the reader's own accounts live. */
function layerColor(layer) {
  if (layer === 'Income') return SEMANTIC.income;
  if (layer === 'Expense') return SEMANTIC.expense;
  return accent().base;
}

/** The tallest column decides the height: a column of twelve nodes squeezed
 *  into 300px is unreadable whatever the other two columns hold. */
const chartHeight = computed(() => {
  const counts = { Income: 0, Asset: 0, Expense: 0 };
  for (const n of nodes.value) counts[n.layer] = (counts[n.layer] || 0) + 1;
  const tallest = Math.max(1, ...Object.values(counts));
  return Math.min(560, Math.max(280, 60 + tallest * 38));
});

const option = computed(() => {
  const { money } = moneyFormatters(props.currency);
  const layerOf = Object.fromEntries(nodes.value.map((n) => [n.name, n.layer]));

  return {
    tooltip: {
      trigger: 'item',
      formatter: (p) => {
        if (p.dataType === 'edge') {
          // A ribbon's share is measured against its OWN column, not against
          // both added together — an income ribbon is a share of what came in,
          // a spending ribbon a share of what went out. One combined
          // denominator would halve every figure here.
          const incoming = layerOf[p.data.source] === 'Income';
          const base = incoming ? inflow.value : outflow.value;
          const share = base ? ((p.data.value / base) * 100).toFixed(1) : '0.0';
          return (
            tooltipTitle(`${p.data.source} &rarr; ${p.data.target}`) +
            tooltipRow(dot(layerColor(layerOf[p.data.source])), 'Moved', money(p.data.value)) +
            tooltipRow(
              dot(CHROME.textFaint),
              incoming ? 'Share of income' : 'Share of spending',
              `${share}%`,
            )
          );
        }
        // A middle-column node's throughput is in PLUS out, which is not its
        // balance — the label has to say which, or it reads as double the money.
        const layer = layerOf[p.name];
        const label = layer === 'Asset' ? 'In and out' : 'Total';
        return tooltipTitle(p.name) + tooltipRow(dot(layerColor(layer)), label,
          money(p.data?.throughput ?? p.value ?? 0));
      },
    },
    series: [
      {
        type: 'sankey',
        top: 12,
        bottom: 12,
        left: 8,
        right: 8,
        nodeWidth: 12,
        nodeGap: 10,
        // Layers come from the server's classification; letting ECharts infer
        // depth would put an account with no income link into the first column.
        draggable: false,
        emphasis: { focus: 'adjacency' },
        label: {
          color: CHROME.textMuted,
          fontSize: 10,
          overflow: 'truncate',
          width: 110,
        },
        lineStyle: { color: 'source', opacity: 0.28, curveness: 0.5 },
        data: nodes.value.map((n) => ({
          name: n.name,
          depth: Math.max(0, ['Income', 'Asset', 'Expense'].indexOf(n.layer)),
          throughput: n.throughput,
          itemStyle: { color: layerColor(n.layer), borderColor: 'transparent' },
          label: { position: n.layer === 'Expense' ? 'left' : 'right' },
        })),
        links: links.value.map((l) => ({
          source: l.source,
          target: l.target,
          value: l.value,
          lineStyle: { color: alpha(layerColor(layerOf[l.source]), 0.3) },
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
        <h3 class="text-sm font-semibold text-gray-900">Money flow</h3>
        <p class="text-xs text-gray-500">
          Income, the accounts it landed in, and the categories it left through
        </p>
      </div>
      <!-- Two figures, never one sum: see the note on inflow/outflow above. -->
      <div v-if="hasData" class="shrink-0 flex gap-6 text-right">
        <div>
          <AmountDisplay :amount="inflow" :currency="currency" class="text-base font-semibold" />
          <div class="text-xs text-gray-500 mt-0.5">income traced in</div>
        </div>
        <div>
          <AmountDisplay :amount="outflow" :currency="currency" class="text-base font-semibold" />
          <div class="text-xs text-gray-500 mt-0.5">spending traced out</div>
        </div>
      </div>
    </header>

    <CsChart
      :option="option"
      :has-data="hasData"
      :height="chartHeight"
      aria-label="Money flow from income accounts through accounts to expense categories"
      empty-text="No income or expense could be traced to an account in this period."
    />

    <!-- The gap between this chart and the totals above it, stated in figures.
         See the note at the top of this file. -->
    <p
      v-if="hasData && excluded.total > 0.005"
      class="mt-2 text-[11px] leading-snug text-gray-500"
    >
      <AmountDisplay :amount="excluded.total" :currency="currency" /> is not drawn
      here: <AmountDisplay :amount="excluded.transfers" :currency="currency" /> moved
      between your own accounts, which changes nothing overall, and
      <AmountDisplay :amount="excluded.other" :currency="currency" /> ran through
      loans, opening balances or refunds that net out, none of which fit the three
      columns above.
      <template v-if="allocated">
        {{ allocated }} {{ allocated === 1 ? 'entry has' : 'entries have' }} several
        sources and several uses, so their ribbons are split in proportion rather
        than recorded that way in the books.
      </template>
    </p>
  </div>
</template>
