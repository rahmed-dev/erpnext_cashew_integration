<script setup>
// f012 c013 — spending limits, from Cashew's non-income budgets.
//
// It shares c009's cycle grid and its filter rule (D3.d): several cycles in
// view get a bar each against the limit line, one cycle gets a single bar.
// THE COLOUR TREATMENT INVERTS. Beating a savings goal is good and c009 turns
// green at 100%; beating a spending limit is the failure the limit exists to
// catch, so here crossing 100% turns the expense hue. The two cards sit beside
// each other and must not teach the reader that "full bar" means one thing on
// the left and the opposite on the right — hence the explicit "over"/"left"
// wording on both, rather than a bare percentage.
//
// The limit is NEVER pro-rated (D3.d) and a cycle with no matching spending is
// a zero rather than a gap: a month where the category went untouched is a
// month under the limit, which is worth seeing.
//
// An unfinished cycle is drawn at reduced opacity and labelled, because a
// half-elapsed month sitting under its limit has not passed anything yet.
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

const limits = computed(() => selectBudgets(props.cycles, { income: false }));
const hasLimits = computed(() => limits.value.length > 0);

/** Inverted against c009: at or over the limit is the expense hue. */
function toneFor(percent) {
  return percent >= 100 ? SEMANTIC.expense : accent().base;
}

const summaries = computed(() =>
  Object.fromEntries(
    limits.value.map((budget) => {
      const list = budget.cycles;
      const spent = list.reduce((sum, c) => sum + (c.spent || 0), 0);
      const closed = list.filter((c) => !c.partial);
      return [budget.budget, {
        spent,
        // Only finished cycles can be said to have blown the limit.
        blown: closed.filter((c) => cyclePercent(c) >= 100).length,
        closed: closed.length,
        multi: list.length > 1,
        partial: list.some((c) => c.partial),
        single: list.length === 1 ? list[0] : null,
      }];
    }),
  ),
);

function seriesOption(budget) {
  const { money, compact } = moneyFormatters(props.currency);
  const rows = budget.cycles;
  const limit = budget.amount || 0;

  return {
    grid: { top: 18, right: 12, bottom: 4, left: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        if (!params?.length) return '';
        const cycle = rows[params[0].dataIndex] || {};
        const percent = cyclePercent(cycle);
        const over = (cycle.spent || 0) - (cycle.amount || 0);
        const out = [tooltipTitle(cycleLabel(cycle))];
        out.push(tooltipRow(dot(toneFor(percent)), 'Spent', money(cycle.spent || 0)));
        out.push(tooltipRow(dot(CHROME.textFaint), 'Limit', money(cycle.amount || 0)));
        out.push(tooltipRow(
          dot('transparent'),
          over > 0 ? 'Over by' : 'Left',
          money(Math.abs(over)),
        ));
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
            opacity: cycle.partial ? 0.45 : 1,
            borderRadius: [3, 3, 0, 0],
          },
        })),
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: CHROME.textFaint, type: 'dashed', width: 1 },
          label: {
            formatter: `Limit ${compact(limit)}`,
            color: CHROME.textFaint,
            fontSize: 10,
            position: 'insideEndTop',
          },
          data: [{ yAxis: limit }],
        },
      },
    ],
  };
}

/**
 * The single-cycle bar, as plain DOM rather than a chart.
 *
 * One value against one threshold is a progress bar; an axis, a grid and a
 * tooltip around a single bar is chrome the reader has to look past. The bar
 * is scaled against the LIMIT, not against the spend, so an overshoot fills it
 * and the amount over is written beside it — a bar rescaled to fit its own
 * overshoot would look identical whether it went over by ten or by ten
 * thousand.
 */
function singleBar(cycle) {
  const percent = cyclePercent(cycle);
  return {
    percent,
    width: `${Math.min(100, Math.max(0, percent))}%`,
    over: (cycle.spent || 0) - (cycle.amount || 0),
    tone: toneFor(percent),
    track: alpha(toneFor(percent), 0.12),
  };
}

function dot(color) {
  return `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${color};margin-right:6px"></span>`;
}
</script>

<template>
  <div v-if="hasLimits" class="rounded-lg border border-gray-200 bg-white p-5">
    <header class="mb-3">
      <h3 class="text-sm font-semibold text-gray-900">Spending limits</h3>
      <p class="text-xs text-gray-500">Against the limit set in Cashew, never pro-rated</p>
    </header>

    <div
      v-for="budget in limits"
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
            :amount="summaries[budget.budget].spent"
            :currency="currency"
            class="text-sm font-semibold"
          />
          <div class="text-xs text-gray-500 mt-0.5">
            <template v-if="summaries[budget.budget].multi">
              over the limit in {{ summaries[budget.budget].blown }} of
              {{ summaries[budget.budget].closed }} finished cycles
            </template>
            <template v-else>spent this cycle</template>
          </div>
        </div>
      </div>

      <CsChart
        v-if="summaries[budget.budget].multi"
        :option="seriesOption(budget)"
        :height="220"
        :aria-label="`Spending against the ${budget.label} limit, one bar per cycle`"
      />

      <!-- Single cycle: a progress bar, not a one-bar chart. See singleBar(). -->
      <div v-else-if="summaries[budget.budget].single" class="mt-3">
        <div
          class="h-3 w-full overflow-hidden rounded-full"
          :style="{ background: singleBar(summaries[budget.budget].single).track }"
        >
          <div
            class="h-full rounded-full"
            :style="{
              width: singleBar(summaries[budget.budget].single).width,
              background: singleBar(summaries[budget.budget].single).tone,
              opacity: summaries[budget.budget].single.partial ? 0.55 : 1,
            }"
          />
        </div>
        <div class="mt-1.5 flex items-baseline justify-between text-xs">
          <span class="text-gray-500">
            {{ singleBar(summaries[budget.budget].single).percent.toFixed(0) }}% of the limit
          </span>
          <span
            :class="singleBar(summaries[budget.budget].single).over > 0
              ? 'text-rose-600 font-medium'
              : 'text-gray-500'"
          >
            <AmountDisplay
              :amount="Math.abs(singleBar(summaries[budget.budget].single).over)"
              :currency="currency"
            />
            {{ singleBar(summaries[budget.budget].single).over > 0 ? 'over' : 'left' }}
          </span>
        </div>
      </div>

      <p v-if="summaries[budget.budget].partial" class="mt-2 text-[11px] leading-snug text-gray-500">
        A cycle here runs past the end of the period you are viewing, so it is drawn
        faded: it has not finished, and a bar under the limit today may still cross
        it. The limit shown is the full cycle limit, not a share of it.
      </p>
    </div>
  </div>
</template>
