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
import CategoryBreakdownCard from '@/components/finance-dashboard/CategoryBreakdownCard.vue';
import AssetBreakdownCard from '@/components/finance-dashboard/AssetBreakdownCard.vue';
import RecentImportsStrip from '@/components/finance-dashboard/RecentImportsStrip.vue';
import DashboardEmptyState from '@/components/finance-dashboard/DashboardEmptyState.vue';

import { useCashewSettings, useDefaultPeriod } from '@/boot';
import { subscribeList } from '@/realtime';
import { resolvePeriodRange } from '@/utils/period';

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
        @tile-click="onTileClick"
      />

      <div class="grid lg:grid-cols-2 gap-4 mt-4">
        <IncomeExpenseChart
          :income="summary.data.income_total"
          :expense="summary.data.expense_total"
          :income-by="summary.data.income_by_account || []"
          :expense-by="summary.data.expense_by_account || []"
          :currency="summary.data.currency"
          :period="summary.data.period"
        />
        <CategoryBreakdownCard
          :income-by="summary.data.income_by_account"
          :expense-by="summary.data.expense_by_account"
          :currency="summary.data.currency"
        />
      </div>

      <AssetBreakdownCard
        :items="summary.data.assets_by_account || []"
        class="mt-4"
      />

      <RecentImportsStrip
        :runs="summary.data.recent_runs"
        class="mt-4"
        @open="(run) => router.push(`/runs/${run.name}`)"
        @new-import="router.push('/runs/new')"
      />
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
