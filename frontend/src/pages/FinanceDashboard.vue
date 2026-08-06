<script setup>
import { reactive, computed, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRouter } from 'vue-router';
import { createResource } from 'frappe-ui';

import PageHeader from '@/components/shared/PageHeader.vue';
import SkeletonBlock from '@/components/shared/SkeletonBlock.vue';

import PeriodSelector from '@/components/finance-dashboard/PeriodSelector.vue';
import CompanySelector from '@/components/finance-dashboard/CompanySelector.vue';
import BalanceTileGrid from '@/components/finance-dashboard/BalanceTileGrid.vue';
import BalanceDetailModal from '@/components/finance-dashboard/BalanceDetailModal.vue';
import IncomeExpenseChart from '@/components/finance-dashboard/IncomeExpenseChart.vue';
import NetWorthChart from '@/components/finance-dashboard/NetWorthChart.vue';
import AccountBalanceChart from '@/components/finance-dashboard/AccountBalanceChart.vue';
import ExpenseTreemapChart from '@/components/finance-dashboard/ExpenseTreemapChart.vue';
import SpendHeatmapChart from '@/components/finance-dashboard/SpendHeatmapChart.vue';
import MoneyFlowSankey from '@/components/finance-dashboard/MoneyFlowSankey.vue';
import SavingsGoalCard from '@/components/finance-dashboard/SavingsGoalCard.vue';
import BudgetVsActualCard from '@/components/finance-dashboard/BudgetVsActualCard.vue';
import CategoryBreakdownCard from '@/components/finance-dashboard/CategoryBreakdownCard.vue';
import AssetBreakdownCard from '@/components/finance-dashboard/AssetBreakdownCard.vue';
import RecentImportsStrip from '@/components/finance-dashboard/RecentImportsStrip.vue';
import DashboardEmptyState from '@/components/finance-dashboard/DashboardEmptyState.vue';

import { useCashewSettings, useDefaultPeriod } from '@/boot';
import { subscribeList } from '@/realtime';
import { resolvePeriodRange } from '@/utils/period';
import { selectBudgets } from '@/utils/budget';

const router = useRouter();
const initialPeriod = resolvePeriodRange('this-month') || useDefaultPeriod();

const state = reactive({
  preset: 'this-month',
  period: { start: initialPeriod?.start || null, end: initialPeriod?.end || null },
  company: useCashewSettings().default_company || null,
  showCompanySelector: false,
  detailModal: { open: false, tile: null },
});

const summary = createResource({
  url: 'cashew_integration.api.dashboard_summary',
  cache: false,
  makeParams: () => ({
    period_start: state.period.start,
    period_end: state.period.end,
    company: state.company,
  }),
  auto: false,
});

// Pre-fetched detail breakdowns for hover panels on Cash & Bank / Receivable / Payable
// tiles. Same endpoint BalanceDetailModal calls on click. Reactive map keyed by tile id.
const tileBreakdowns = reactive({ cash_bank: null, receivable: null, payable: null });
const tileDetailResources = {};
for (const tile of ['cash_bank', 'receivable', 'payable']) {
  tileDetailResources[tile] = createResource({
    url: 'cashew_integration.api.balance_tile_detail',
    cache: false,
    auto: false,
    makeParams: () => ({ company: state.company, tile, as_of: state.period.end }),
    onSuccess: (data) => { tileBreakdowns[tile] = data; },
  });
}

function refetch() {
  if (!state.period.start || !state.period.end) return;
  summary.reload();
  if (state.company && state.period.end) {
    for (const r of Object.values(tileDetailResources)) r.reload();
  }
}

const companyCountResource = createResource({
  url: 'frappe.client.get_count',
  cache: false,
  params: { doctype: 'Company' },
  onSuccess: (count) => { state.showCompanySelector = Number(count || 0) > 1; },
});

const isEmpty = computed(() => {
  const d = summary.data;
  if (!d) return false;
  const tiles = d.balance_tiles || {};
  const tilesAllZero = ['cash_bank', 'receivable', 'payable', 'net_for_period']
    .every((k) => Math.abs(tiles[k]?.amount || 0) < 0.01);
  return (d.income_total || 0) === 0
    && (d.expense_total || 0) === 0
    && tilesAllZero
    && (d.recent_runs?.length || 0) === 0;
});

// The goals section is dropped entirely, heading and all, when Cashew carries
// no usable budget — a section title over two blank cards reads as a surface
// that failed to load. Both cards apply the same filter internally.
const budgetCycles = computed(() => summary.data?.budget_cycles || []);
const hasBudgets = computed(() =>
  selectBudgets(budgetCycles.value, { income: true }).length > 0
  || selectBudgets(budgetCycles.value, { income: false }).length > 0,
);

let unsubList = null;
let realtimeTimer = null;

onMounted(() => {
  companyCountResource.fetch();
  refetch();
  unsubList = subscribeList('Cashew Import Run', () => {
    if (realtimeTimer) clearTimeout(realtimeTimer);
    realtimeTimer = setTimeout(refetch, 2000);
  });
});

onBeforeUnmount(() => {
  unsubList?.();
  if (realtimeTimer) clearTimeout(realtimeTimer);
});

watch(() => [state.period.start, state.period.end, state.company], refetch);

function onPeriodPreset(p) { state.preset = p; }
function onPeriod(range) { state.period = range || { start: null, end: null }; }
function onCompany(value) { state.company = value; }

function onTileClick(tileId) {
  if (!tileId) return;
  state.detailModal.tile = tileId;
  state.detailModal.open = true;
}
</script>

<template>
  <div class="px-4 md:px-6 py-6 max-w-7xl mx-auto">
    <PageHeader title="Finance Dashboard" subtitle="Period overview" :border="false">
      <template #actions>
        <PeriodSelector
          :preset="state.preset"
          :period="state.period"
          @update:preset="onPeriodPreset"
          @update:period="onPeriod"
        />
        <CompanySelector
          v-if="state.showCompanySelector"
          :modelValue="state.company"
          @update:modelValue="onCompany"
        />
      </template>
    </PageHeader>

    <template v-if="summary.loading && !summary.data">
      <BalanceTileGrid :data="null" />
      <div class="grid lg:grid-cols-2 gap-4 mt-4">
        <SkeletonBlock class="h-72" />
        <SkeletonBlock class="h-72" />
      </div>
      <SkeletonBlock class="h-32 mt-4" />
    </template>

    <DashboardEmptyState v-else-if="isEmpty" @new-import="router.push('/runs/new')" />

    <template v-else-if="summary.data">
      <BalanceTileGrid
        :data="summary.data.balance_tiles"
        :currency="summary.data.currency"
        :breakdowns="tileBreakdowns"
        :expense="summary.data.expense_total"
        :invoices="summary.data.invoices"
        @tile-click="onTileClick"
      />

      <!--
        c011 — the dashboard is FOUR named sections, not one undifferentiated
        scroll of cards. Eight charts in a row all look equally important and
        the reader has no way in; a heading tells them which question each
        stretch answers, and lets them skip the ones they are not asking.
        The order is the order the questions arrive in: what do I have, how did
        it move, where did it go, am I inside my own targets.

        Every row is `grid lg:grid-cols-2` — ONE column below the lg breakpoint,
        not a shrunken desktop grid (f010 D2.c). Nothing here relies on a
        neighbour being beside it rather than above it.
      -->
      <section class="mt-8">
        <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-500">Trends</h2>
        <p class="text-xs text-gray-400 mt-0.5">How income and balances moved over the period</p>

        <div class="grid lg:grid-cols-2 gap-4 mt-3">
          <IncomeExpenseChart
            :series="summary.data.series"
            :income="summary.data.income_total"
            :expense="summary.data.expense_total"
            :currency="summary.data.currency"
          />
          <CategoryBreakdownCard
            :income-by="summary.data.income_by_account"
            :expense-by="summary.data.expense_by_account"
            :currency="summary.data.currency"
          />
        </div>

        <!-- Balance-sheet pair: the net total on the left, the accounts it is
             made of on the right. -->
        <div class="grid lg:grid-cols-2 gap-4 mt-4">
          <NetWorthChart
            :series="summary.data.series"
            :currency="summary.data.currency"
          />
          <AccountBalanceChart
            :series="summary.data.series"
            :currency="summary.data.currency"
          />
        </div>
      </section>

      <section class="mt-8">
        <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-500">Where it went</h2>
        <p class="text-xs text-gray-400 mt-0.5">The same spending by category, by day, and by route</p>

        <!-- Expense pair: the composition of the spending on the left, its
             distribution over time on the right. -->
        <div class="grid lg:grid-cols-2 gap-4 mt-3">
          <ExpenseTreemapChart
            :series="summary.data.series"
            :currency="summary.data.currency"
          />
          <SpendHeatmapChart
            :days="summary.data.daily_spend || []"
            :currency="summary.data.currency"
          />
        </div>

        <!-- Full width, alone: the sankey carries three columns of labels and
             is the one chart here that is unreadable at half the page. -->
        <MoneyFlowSankey
          :flow="summary.data.money_flow"
          :currency="summary.data.currency"
          class="mt-4"
        />
      </section>

      <section v-if="hasBudgets" class="mt-8">
        <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-500">Goals and limits</h2>
        <p class="text-xs text-gray-400 mt-0.5">Against the budgets set in Cashew, on their own cycles</p>

        <div class="grid lg:grid-cols-2 gap-4 mt-3 items-start">
          <SavingsGoalCard
            :cycles="summary.data.budget_cycles || []"
            :currency="summary.data.currency"
          />
          <BudgetVsActualCard
            :cycles="summary.data.budget_cycles || []"
            :currency="summary.data.currency"
          />
        </div>
      </section>

      <section class="mt-8">
        <h2 class="text-xs font-semibold uppercase tracking-wide text-gray-500">Holdings and imports</h2>
        <p class="text-xs text-gray-400 mt-0.5">What the balances are made of, and where the data came from</p>

        <AssetBreakdownCard
          :items="summary.data.assets_by_account || []"
          class="mt-3"
        />

        <RecentImportsStrip
          :runs="summary.data.recent_runs"
          class="mt-4"
          @open="(run) => router.push(`/runs/${run.name}`)"
          @new-import="router.push('/runs/new')"
        />
      </section>
    </template>

    <BalanceDetailModal
      :open="state.detailModal.open"
      :tile="state.detailModal.tile"
      :company="state.company"
      :as-of="state.period.end"
      @update:open="(v) => state.detailModal.open = v"
    />
  </div>
</template>
