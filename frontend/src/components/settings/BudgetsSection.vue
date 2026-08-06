<script setup>
// f012 c015 — the budgets-only sync surface.
//
// It lives in Settings, not in the imports flow, on purpose: this is a
// configuration fetch that happens to read a backup file. It creates no Cashew
// Import Run, and a config sync that showed up in the import history would teach
// the user to distrust that history (c015 note).
//
// The result is reported as created / updated / unchanged rather than a single
// "imported" number, because the whole point of the action is that it is re-run
// after editing a budget in Cashew — "2 budgets imported" every time says nothing
// about whether the edit landed.
import { reactive, computed } from 'vue';
import { toast, Button, createResource } from 'frappe-ui';
import { RefreshCw, TriangleAlert } from 'lucide-vue-next';

import CsvDropzone from '@/components/run-workspace/upload/CsvDropzone.vue';
import DeskLinkRow from './DeskLinkRow.vue';

const props = defineProps({
  company: { type: [String, null], default: null },
  disabled: { type: Boolean, default: false },
});

const state = reactive({
  fileUrl: null,
  result: null,
});

const sync = createResource({
  url: 'cashew_integration.api.sync_budgets',
  makeParams: () => ({ file_url: state.fileUrl, company: props.company || undefined }),
  onSuccess: (data) => {
    state.result = data;
    const changed = (data?.created || 0) + (data?.updated || 0);
    if (changed) toast.success(`${changed} budget${changed === 1 ? '' : 's'} synced`);
    else if (data?.total) toast.success('Budgets already up to date');
    else toast.info('This backup contains no budgets');
  },
});

const canSync = computed(() => !!state.fileUrl && !props.disabled && !sync.loading);
const skipped = computed(() => state.result?.skipped || []);

function run() {
  if (!canSync.value) return;
  state.result = null;
  sync.submit();
}

/** The mapping members that blocked a budget, as one readable line. */
function blockedBy(entry) {
  return (entry.unresolved || [])
    .map((u) => {
      if (u.kind === 'account') return `account “${u.account_name || u.pk}”`;
      if (u.kind === 'category') {
        const name = [u.category, u.sub_category].filter(Boolean).join(' › ');
        return `category “${name || u.pk}”`;
      }
      if (u.kind === 'start_date') return 'no start date';
      if (u.kind === 'empty_scope') return 'nothing in scope is mapped';
      return u.kind;
    })
    .join(', ');
}
</script>

<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5">
    <header class="mb-4">
      <h2 class="text-base font-semibold text-gray-900">Budgets</h2>
      <p class="text-sm text-gray-500 mt-1">
        Pull budgets and savings goals from a Cashew backup. Reads only the budgets —
        no transactions are imported and no ledger entries are created. Safe to re-run
        whenever you change a budget in Cashew.
      </p>
    </header>

    <CsvDropzone
      v-model="state.fileUrl"
      source-type="SQLite"
      :disabled="disabled || sync.loading"
    />

    <div class="mt-3 flex items-center gap-3">
      <Button
        variant="solid"
        :icon-left="RefreshCw"
        :loading="sync.loading"
        :disabled="!canSync"
        @click="run"
      >
        Sync budgets
      </Button>
      <span v-if="disabled" class="text-xs text-gray-500">
        You need write access to Cashew Settings to sync budgets.
      </span>
    </div>

    <div v-if="state.result" class="mt-4 rounded-lg border border-gray-200 bg-gray-50 p-3">
      <div class="flex flex-wrap gap-x-6 gap-y-1 text-sm text-gray-700">
        <span><b class="tabular-nums">{{ state.result.created }}</b> created</span>
        <span><b class="tabular-nums">{{ state.result.updated }}</b> updated</span>
        <span><b class="tabular-nums">{{ state.result.unchanged }}</b> unchanged</span>
        <span class="text-gray-500">of {{ state.result.total }} in the backup</span>
      </div>

      <div v-if="skipped.length" class="mt-3 border-t border-gray-200 pt-3">
        <div class="flex items-start gap-2">
          <TriangleAlert :size="14" class="mt-0.5 shrink-0 text-amber-600" />
          <div class="min-w-0">
            <p class="text-sm font-medium text-gray-900">
              {{ skipped.length }} budget{{ skipped.length === 1 ? '' : 's' }} not imported
            </p>
            <p class="text-xs text-gray-500">
              A budget is only imported once every account and category in its scope is
              mapped. An unmapped member would leave a hole in the budget's actuals, and
              the figure would read under limit when the limit had in fact been blown.
              Map these, then sync again.
            </p>
            <ul class="mt-2 space-y-1">
              <li v-for="s in skipped" :key="s.budget_pk" class="text-xs text-gray-700">
                <span class="font-medium">{{ s.budget_name || s.budget_pk }}</span>
                <span class="text-gray-500"> — {{ blockedBy(s) }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <div class="mt-4 divide-y divide-gray-100 border-t border-gray-100">
      <DeskLinkRow
        label="Cashew Budget"
        href="/app/cashew-budget"
        sublabel="Every budget synced from Cashew, with its resolved scope."
      />
    </div>
  </section>
</template>
