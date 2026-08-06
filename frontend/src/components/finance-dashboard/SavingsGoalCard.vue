<script setup>
// f012 c009 — savings goals, from Cashew's income budgets.
//
// D3.d decides the shape, and it is the filter that decides, not a setting: a
// filter spanning SEVERAL cycles gets a bar per cycle against the target line,
// because the question then is "do I hit this most months"; a filter spanning
// ONE cycle or less gets the gauge, because the question is "where am I in
// this one". Both come from the same server-side cycle grid — cycle length is
// the budget's own reoccurrence and period_length, never assumed monthly.
//
// THE TARGET IS NEVER PRO-RATED (D3.d). Viewing a monthly goal through half a
// month does not halve the target; it shows the whole target and marks the
// cycle unfinished. A pro-rated figure would be one no one ever set.
//
// OVER-ACHIEVEMENT IS SHOWN, NOT CLIPPED. The gauge's axis extends past 100%
// when the goal is beaten, since capping the needle at the target would make
// beating it by half look identical to just reaching it. A cycle with no
// matching transactions is a zero, not a gap — a month where nothing was saved
// is a missed target, and drawing it as absent hides the miss.
//
// The card renders nothing at all when there is no goal, or when the target is
// zero: a dial at zero out of zero is not information.
import { computed } from 'vue';
import CsChart from '@/components/shared/CsChart.vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';
import {
  SEMANTIC, CHROME, alpha, accent,
  moneyAxis, categoryAxis, moneyFormatters, tooltipRow, tooltipTitle,
} from '@/charts/theme';
import { selectBudgets, cycleLabel, cyclePercent, reoccurrenceLabel } from '@/utils/budget';

const props = defineProps({
  // `dashboard_summary.budget_cycles`.
  cycles: { type: Array, default: () => [] },
  currency: { type: String, default: 'PKR' },
});

const goals = computed(() => selectBudgets(props.cycles, { income: true }));
const hasGoals = computed(() => goals.value.length > 0);

/** Hit colour when the target is met, accent while still short of it. */
function toneFor(percent) {
  return percent >= 100 ? SEMANTIC.income : accent().base;
}

function gaugeOption(budget) {
  const cycle = budget.cycles[0];
  const { money } = moneyFormatters(props.currency);
  const percent = cyclePercent(cycle);
  // Room above 100 so beating the goal is visible as distance, not as a needle
  // pinned to the end of the scale.
  const max = Math.max(100, Math.ceil(percent / 10) * 10);
  const tone = toneFor(percent);

  return {
    tooltip: { show: false },
    series: [
      {
        type: 'gauge',
        startAngle: 200,
        endAngle: -20,
        min: 0,
        max,
        radius: '96%',
        center: ['50%', '62%'],
        splitNumber: 4,
        pointer: { show: false },
        progress: {
          show: true,
          width: 14,
          roundCap: true,
          itemStyle: { color: tone },
        },
        axisLine: {
          roundCap: true,
          lineStyle: { width: 14, color: [[1, alpha(tone, 0.12)]] },
        },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: {
          color: CHROME.textFaint,
          fontSize: 9,
          distance: -4,
          formatter: (v) => `${Math.round(v)}%`,
        },
        anchor: { show: false },
        title: { show: false },
        detail: {
          offsetCenter: [0, '-2%'],
          color: CHROME.text,
          fontSize: 20,
          fontWeight: 600,
          formatter: () => `${percent.toFixed(0)}%`,
        },
        data: [{ value: Math.max(0, percent) }],
      },
    ],
    // Written under the dial so the two figures the percentage came from are
    // never left for the reader to reconstruct.
    graphic: {
      type: 'text',
      left: 'center',
      bottom: 2,
      style: {
        text: `${money(cycle.spent || 0)} of ${money(cycle.amount || 0)}`,
        fill: CHROME.textMuted,
        fontSize: 11,
      },
    },
  };
}

function seriesOption(budget) {
  const { money, compact } = moneyFormatters(props.currency);
  const rows = budget.cycles;
  const target = budget.amount || 0;

  return {
    grid: { top: 18, right: 12, bottom: 4, left: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        if (!params?.length) return '';
        const cycle = rows[params[0].dataIndex] || {};
        const percent = cyclePercent(cycle);
        const out = [tooltipTitle(cycleLabel(cycle))];
        out.push(tooltipRow(dot(toneFor(percent)), 'Saved', money(cycle.spent || 0)));
        out.push(tooltipRow(dot(CHROME.textFaint), 'Target', money(cycle.amount || 0)));
        out.push(tooltipRow(dot('transparent'), 'Of target', `${percent.toFixed(0)}%`));
        if (cycle.partial) {
          out.push(`<div style="color:${CHROME.textFaint};margin-top:4px">Cycle still running</div>`);
        }
        return out.join('');
      },
    },
    xAxis: categoryAxis(rows.map(cycleLabel), {
      axisLabel: { color: CHROME.axis, fontSize: 10, hideOverlap: true },
    }),
    yAxis: moneyAxis(props.currency, {
      axisLabel: { color: CHROME.axis, fontSize: 10, formatter: (v) => compact(v) },
    }),
    series: [
      {
        type: 'bar',
        barMaxWidth: 34,
        data: rows.map((cycle) => ({
          value: Math.max(0, cycle.spent || 0),
          itemStyle: {
            color: toneFor(cyclePercent(cycle)),
            // An unfinished cycle is drawn hollow: a half-elapsed month that
            // looks like a solid miss is a lie about a month still in progress.
            opacity: cycle.partial ? 0.45 : 1,
            borderRadius: [3, 3, 0, 0],
          },
        })),
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: CHROME.textFaint, type: 'dashed', width: 1 },
          label: {
            formatter: `Target ${compact(target)}`,
            color: CHROME.textFaint,
            fontSize: 10,
            position: 'insideEndTop',
          },
          data: [{ yAxis: target }],
        },
      },
    ],
  };
}

/** Per-goal headline figures, computed once rather than per template read. */
const summaries = computed(() =>
  Object.fromEntries(
    goals.value.map((budget) => {
      const list = budget.cycles;
      return [budget.budget, {
        saved: list.reduce((sum, c) => sum + (c.spent || 0), 0),
        met: list.filter((c) => !c.partial && cyclePercent(c) >= 100).length,
        finished: list.filter((c) => !c.partial).length,
        multi: list.length > 1,
        partial: list.some((c) => c.partial),
      }];
    }),
  ),
);

function dot(color) {
  return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px"></span>`;
}
</script>

<template>
  <div v-if="hasGoals" class="rounded-lg border border-gray-200 bg-white p-5">
    <header class="mb-3">
      <h3 class="text-sm font-semibold text-gray-900">Savings goals</h3>
      <p class="text-xs text-gray-500">Against the target set in Cashew, never pro-rated</p>
    </header>

    <div
      v-for="budget in goals"
      :key="budget.budget"
      class="border-t border-gray-100 pt-3 mt-3 first:border-t-0 first:pt-0 first:mt-0"
    >
      <div class="flex items-start justify-between gap-4">
        <div>
          <div class="text-sm font-medium text-gray-900">{{ budget.label }}</div>
          <div class="text-xs text-gray-500">
            <AmountDisplay :amount="budget.amount" :currency="currency" />
            {{ reoccurrenceLabel(budget) }}
          </div>
        </div>
        <div class="text-right shrink-0">
          <AmountDisplay
            :amount="summaries[budget.budget].saved"
            :currency="currency"
            class="text-sm font-semibold"
          />
          <div class="text-xs text-gray-500 mt-0.5">
            <template v-if="summaries[budget.budget].multi">
              {{ summaries[budget.budget].met }} of {{ summaries[budget.budget].finished }} cycles met
            </template>
            <template v-else>saved this cycle</template>
          </div>
        </div>
      </div>

      <CsChart
        :option="summaries[budget.budget].multi ? seriesOption(budget) : gaugeOption(budget)"
        :height="summaries[budget.budget].multi ? 220 : 190"
        :aria-label="`Savings progress for ${budget.label}`"
      />

      <p v-if="summaries[budget.budget].partial" class="text-[11px] leading-snug text-gray-500">
        A cycle here runs past the end of the period you are viewing, so its figure
        covers only the part inside it. The target is the full cycle target either
        way — it is not scaled down to match a shorter view.
      </p>
    </div>
  </div>
</template>
