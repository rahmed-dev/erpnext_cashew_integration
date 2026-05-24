<script setup>
import { reactive, ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { createResource, Button } from 'frappe-ui';
import { Plus } from 'lucide-vue-next';

import PageHeader from '@/components/shared/PageHeader.vue';
import FilterBar from '@/components/imports-list/FilterBar.vue';
import RunsTable from '@/components/imports-list/RunsTable.vue';
import RunsCardList from '@/components/imports-list/RunsCardList.vue';
import Pagination from '@/components/imports-list/Pagination.vue';
import EmptyAllRuns from '@/components/imports-list/EmptyAllRuns.vue';
import EmptyFilterMiss from '@/components/imports-list/EmptyFilterMiss.vue';

import { useIsMobile } from '@/state/useIsMobile';
import { subscribeList } from '@/realtime';
import { resolvePeriodRange } from '@/utils/period';
import { useCashewSettings } from '@/boot';

const PAGE_SIZE = 25;
const STORAGE_KEY = 'cashew:imports:filters';
const router = useRouter();
const isMobile = useIsMobile();

const defaultCompany = useCashewSettings().default_company || null;

function freshFilters() {
  return { status: [], period: 'any', period_range: null, company: defaultCompany, search: '' };
}

function loadPersistedFilters() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return { ...freshFilters(), ...parsed };
  } catch {
    return null;
  }
}

const state = reactive({
  filters: loadPersistedFilters() || freshFilters(),
  sort: { column: 'modified', dir: 'desc' },
  page: { start: 0, length: PAGE_SIZE },
  rows: [],
  total: 0,
  loading: true,
  error: null,
});

const pulseMap = ref({});

function buildFilterArray() {
  const f = state.filters;
  const out = [];
  if (f.status?.length) out.push(['status', 'in', f.status]);
  const range = resolvePeriodRange(f.period, f.period_range);
  if (range) {
    out.push(['period_start', '<=', range.end]);
    out.push(['period_end', '>=', range.start]);
  }
  if (f.company) out.push(['company', '=', f.company]);
  const term = (f.search || '').trim();
  if (term) out.push(['name', 'like', `%${term}%`]);
  return out;
}

const runsResource = createResource({
  url: 'frappe.client.get_list',
  cache: false,
  makeParams: () => ({
    doctype: 'Cashew Import Run',
    fields: [
      'name', 'status', 'company',
      'period_start', 'period_end',
      'rows_total', 'rows_valid', 'rows_failed', 'rows_posted', 'rows_skipped',
      'modified', 'diagnostics_file',
    ],
    filters: buildFilterArray(),
    order_by: `${state.sort.column} ${state.sort.dir}`,
    limit_start: state.page.start,
    limit_page_length: state.page.length,
  }),
  onSuccess: (rows) => {
    state.rows = rows || [];
    state.loading = false;
    state.error = null;
  },
  onError: (err) => {
    state.loading = false;
    state.error = err;
  },
});

const countResource = createResource({
  url: 'frappe.client.get_count',
  cache: false,
  makeParams: () => ({
    doctype: 'Cashew Import Run',
    filters: buildFilterArray(),
  }),
  onSuccess: (n) => {
    state.total = typeof n === 'number' ? n : (n?.message ?? 0);
  },
});

function refetch() {
  state.loading = true;
  runsResource.reload();
  countResource.reload();
}

const hasActiveFilters = computed(() => Boolean(
  state.filters.status.length ||
  state.filters.period !== 'any' ||
  state.filters.company ||
  (state.filters.search || '').trim(),
));

function patchFilters(next) {
  state.filters = { ...next };
  state.page.start = 0;
}
function clearFilters() {
  state.filters = freshFilters();
  state.page.start = 0;
}
function onSort(s) {
  state.sort = { ...s };
  state.page.start = 0;
}
function onPage(p) {
  state.page = { ...p };
}
function onRowAction(e) {
  if (e.type === 'open') {
    router.push(`/runs/${e.row.name}`);
  } else if (e.type === 'diagnostics') {
    if (e.row.diagnostics_file) window.open(e.row.diagnostics_file, '_blank', 'noopener');
  }
  // 'revert' and 'cancel' deferred to c006 workspace (real implementation
  // routes there for confirmation + state machine handling).
  if (e.type === 'revert' || e.type === 'cancel') {
    router.push(`/runs/${e.row.name}`);
  }
}

// Debounce search; immediate for all other filters.
let searchTimer = null;
watch(() => state.filters.search, () => {
  if (searchTimer) clearTimeout(searchTimer);
  searchTimer = setTimeout(refetch, 250);
});
watch(
  () => [state.filters.status, state.filters.period, state.filters.period_range, state.filters.company],
  () => refetch(),
  { deep: true },
);
watch(() => state.sort, () => refetch(), { deep: true });
watch(() => state.page.start, () => refetch());

watch(
  () => state.filters,
  (f) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(f));
    } catch {
      // localStorage may be unavailable (private mode, quota); silently skip.
    }
  },
  { deep: true },
);

// Realtime: row patches in place; new runs prepend on page 1 with pulse.
let unsubList = null;
let countRefreshTimer = null;
function onRunChange(payload) {
  if (!payload || payload.doctype !== 'Cashew Import Run') return;
  const name = payload.name || payload.docname;
  if (!name) return;
  const idx = state.rows.findIndex((r) => r.name === name);
  if (idx >= 0) {
    state.rows[idx] = { ...state.rows[idx], ...(payload.doc || payload.row || {}) };
    pulseMap.value[name] = Date.now() + 500;
    setTimeout(() => { delete pulseMap.value[name]; }, 520);
  } else if (state.page.start === 0 && payload.doc) {
    state.rows = [payload.doc, ...state.rows].slice(0, state.page.length);
    pulseMap.value[name] = Date.now() + 500;
    setTimeout(() => { delete pulseMap.value[name]; }, 520);
  }
  if (countRefreshTimer) clearTimeout(countRefreshTimer);
  countRefreshTimer = setTimeout(() => countResource.reload(), 1000);
}

onMounted(() => {
  refetch();
  unsubList = subscribeList('Cashew Import Run', onRunChange);
});
onBeforeUnmount(() => {
  if (unsubList) unsubList();
  if (searchTimer) clearTimeout(searchTimer);
  if (countRefreshTimer) clearTimeout(countRefreshTimer);
});

const subtitle = computed(() => {
  if (state.loading && !state.rows.length) return null;
  return state.total === 1 ? '1 run total' : `${state.total} runs total`;
});
</script>

<template>
  <div class="px-4 md:px-6 py-6 max-w-7xl mx-auto">
    <PageHeader title="Imports" :subtitle="subtitle">
      <template #actions>
        <Button variant="solid" theme="accent" @click="router.push('/runs/new')">
          <template #prefix><Plus :size="14" /></template>
          New Import
        </Button>
      </template>
    </PageHeader>

    <FilterBar :filters="state.filters" @update:filters="patchFilters" @clear="clearFilters" />

    <EmptyAllRuns v-if="!state.loading && state.total === 0 && !hasActiveFilters" />

    <EmptyFilterMiss
      v-else-if="!state.loading && state.rows.length === 0 && hasActiveFilters"
      @clear="clearFilters"
    />

    <component
      v-else
      :is="isMobile ? RunsCardList : RunsTable"
      :rows="state.rows"
      :loading="state.loading"
      :sort="state.sort"
      :pulseMap="pulseMap"
      @sort="onSort"
      @action="onRowAction"
    />

    <Pagination
      v-if="state.total > PAGE_SIZE"
      :start="state.page.start"
      :length="state.page.length"
      :total="state.total"
      @page="onPage"
    />
  </div>
</template>
