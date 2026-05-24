<script setup>
import { reactive, ref, computed, watch, onMounted } from 'vue';
import { frappeRequest, toast } from 'frappe-ui';

import WorkbenchToolbar from '@/components/run-workspace/workbench/WorkbenchToolbar.vue';
import ActiveFilterChips from '@/components/run-workspace/workbench/ActiveFilterChips.vue';
import RowsTable from '@/components/run-workspace/workbench/RowsTable.vue';
import RowsCardList from '@/components/run-workspace/workbench/RowsCardList.vue';
import SelectionFooter from '@/components/run-workspace/workbench/SelectionFooter.vue';
import InlineRowDrawer from '@/components/run-workspace/workbench/InlineRowDrawer.vue';
import ValidationFixModal from '@/components/run-workspace/workbench/ValidationFixModal.vue';
import BulkPartyModal from '@/components/run-workspace/workbench/BulkPartyModal.vue';

import { COLUMN_PRESETS, pickInitialPreset } from '@/components/run-workspace/workbench/registries/columns';
import { applyFilters } from '@/components/run-workspace/workbench/registries/filters';
import { BULK_ACTIONS } from '@/components/run-workspace/workbench/registries/bulkActions';
import { useIsMobile } from '@/state/useIsMobile';

const props = defineProps({
  doc: { type: Object, required: true },
  rows: { type: Array, default: () => [] },
  runName: { type: String, required: true },
});
const emit = defineEmits(['reload']);

const isMobile = useIsMobile();

const editable = computed(() => props.doc?.status === 'Validated');

const state = reactive({
  search: '',
  filters: {},
  preset: 'Compact',
  visibleColumns: [],
  sort: null,
  selected: new Set(),
});

const recentPatches = ref(new Set());

watch(() => state.preset, (p) => {
  state.visibleColumns = COLUMN_PRESETS[p] ? [...COLUMN_PRESETS[p]] : state.visibleColumns;
}, { immediate: false });

watch(() => props.rows, () => {
  for (const idx of [...state.selected]) {
    if (!props.rows.some((r) => r.row_idx === idx)) state.selected.delete(idx);
  }
}, { deep: false });

onMounted(() => {
  state.preset = pickInitialPreset(props.rows);
  state.visibleColumns = [...COLUMN_PRESETS[state.preset]];
});

const filteredRows = computed(() => applyFilters(props.rows, state.filters, state.search));

const sortedRows = computed(() => {
  if (!state.sort?.column || !state.sort?.dir) return filteredRows.value;
  const { column, dir } = state.sort;
  const copy = [...filteredRows.value];
  copy.sort((a, b) => {
    const av = a[column] ?? '';
    const bv = b[column] ?? '';
    if (av < bv) return dir === 'asc' ? -1 : 1;
    if (av > bv) return dir === 'asc' ? 1 : -1;
    return 0;
  });
  return copy;
});

const selectedRows = computed(() => props.rows.filter((r) => state.selected.has(r.row_idx)));

function toggleSelect(idx) {
  if (state.selected.has(idx)) state.selected.delete(idx);
  else state.selected.add(idx);
}
function selectAll(value) {
  if (value) sortedRows.value.forEach((r) => state.selected.add(r.row_idx));
  else state.selected.clear();
}
function clearSelection() { state.selected.clear(); }

function removeFacet(facetId) {
  const next = { ...state.filters };
  delete next[facetId];
  state.filters = next;
}
function clearAllFilters() { state.filters = {}; }

const drawerRow = ref(null);
const fixRow = ref(null);
const fixOpen = ref(false);
const bulkOpen = ref(false);
const bulkBusy = ref(null);

function onRowAction({ action, row }) {
  if (action === 'fix') { fixRow.value = row; fixOpen.value = true; }
  else if (action === 'view-json') { drawerRow.value = row; }
  else if (action === 'open-posted' && row.posted_docname) {
    const slug = (row.posted_doctype || '').toLowerCase().replace(/ /g, '-');
    window.open(`/app/${slug}/${row.posted_docname}`, '_blank');
  } else if (action === 'revalidate') {
    revalidateSelected([row.row_idx]);
  }
}

async function revalidateSelected(indices) {
  try {
    await frappeRequest({
      url: 'cashew_integration.api.row_explorer_revalidate',
      method: 'POST',
      params: { run_name: props.runName, row_indices: indices },
    });
    toast.success(`Re-validated ${indices.length} row${indices.length === 1 ? '' : 's'}.`);
    emit('reload');
  } catch (_e) { /* interceptor toasted */ }
}

async function onBulkAction(action) {
  if (action.openModal === 'BulkPartyModal') {
    bulkOpen.value = true;
    return;
  }
  if (action.method) {
    bulkBusy.value = action.id;
    try {
      const params = action.extractParams({ runName: props.runName, selectedRows: selectedRows.value });
      await frappeRequest({
        url: `cashew_integration.api.${action.method}`,
        method: 'POST',
        params,
      });
      toast.success(action.toast({ selectedRows: selectedRows.value }));
      clearSelection();
      emit('reload');
    } catch (_e) { /* interceptor toasted */ }
    finally { bulkBusy.value = null; }
  }
}

async function validateRun() {
  try {
    await frappeRequest({
      url: 'cashew_integration.api.validate_import',
      method: 'POST',
      params: { run_name: props.runName },
    });
    emit('reload');
  } catch (_e) { /* interceptor toasted */ }
}

defineExpose({ markRecentPatch });
function markRecentPatch(idx) {
  recentPatches.value.add(idx);
  setTimeout(() => {
    recentPatches.value.delete(idx);
    recentPatches.value = new Set(recentPatches.value);
  }, 500);
  recentPatches.value = new Set(recentPatches.value);
}
</script>

<template>
  <div class="space-y-3">
    <WorkbenchToolbar
      :search="state.search"
      :filters="state.filters"
      :preset="state.preset"
      :visible-columns="state.visibleColumns"
      :rows="rows"
      :editable="editable"
      @update:search="(v) => state.search = v"
      @update:filters="(v) => state.filters = v"
      @update:preset="(v) => state.preset = v"
      @update:visible-columns="(v) => state.visibleColumns = v"
      @validate="validateRun"
    />
    <ActiveFilterChips
      :filters="state.filters"
      :search="state.search"
      @remove="removeFacet"
      @clear-all="clearAllFilters"
      @clear-search="state.search = ''"
    />

    <RowsCardList
      v-if="isMobile"
      :rows="sortedRows"
      :selected="state.selected"
      :editable="editable"
      :recent-patches="recentPatches"
      @select-toggle="toggleSelect"
      @row-action="onRowAction"
      @row-click="(r) => drawerRow = r"
    />
    <RowsTable
      v-else
      :rows="sortedRows"
      :visible-columns="state.visibleColumns"
      :selected="state.selected"
      :editable="editable"
      :run-name="runName"
      :sort="state.sort"
      :recent-patches="recentPatches"
      @select-toggle="toggleSelect"
      @select-all="selectAll"
      @row-action="onRowAction"
      @row-click="(r) => drawerRow = r"
      @sort="(s) => state.sort = s"
      @row-saved="emit('reload')"
    />

    <SelectionFooter
      :count="state.selected.size"
      :actions="BULK_ACTIONS.filter((a) => a.enabledWhen({ selectedRows, editable }))"
      :busy="bulkBusy"
      @action="onBulkAction"
      @clear="clearSelection"
    />

    <InlineRowDrawer :row="drawerRow" @close="drawerRow = null" />

    <ValidationFixModal
      :row="fixRow"
      :run-name="runName"
      :open="fixOpen"
      @update:open="(v) => fixOpen = v"
      @saved="emit('reload')"
    />

    <BulkPartyModal
      :open="bulkOpen"
      :run-name="runName"
      :selected-rows="selectedRows"
      @update:open="(v) => bulkOpen = v"
      @saved="() => { clearSelection(); emit('reload'); }"
    />
  </div>
</template>
