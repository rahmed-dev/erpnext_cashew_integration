<script setup>
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { Button, toast, frappeRequest } from 'frappe-ui';
import { ChevronLeft, ExternalLink, Radio, Loader2 } from 'lucide-vue-next';

import StatusPill from '@/components/shared/StatusPill.vue';
import ConfirmDialog from '@/components/shared/ConfirmDialog.vue';
import { useRealtimeStatus } from '@/state/useRealtimeStatus';
import { formatRange } from '@/utils/period';

const props = defineProps({
  doc: { type: [Object, null], default: null },
  runName: { type: [String, null], default: null },
  loading: { type: Boolean, default: false },
});
const emit = defineEmits(['reload']);

const router = useRouter();
const realtimeStatus = useRealtimeStatus();
const busy = ref(null);
const confirmState = ref(null);

const status = computed(() => props.doc?.status || (props.runName ? null : 'Draft'));
const inFlight = computed(() => ['Queued', 'Processing', 'Reverting'].includes(status.value));
const periodFmt = computed(() => formatRange(props.doc?.period_start, props.doc?.period_end));

const RUN_ACTIONS = {
  Draft: [
    { id: 'parse',   label: 'Parse',         primary: true,  method: 'parse_and_preview' },
  ],
  Parsed: [
    { id: 'reparse',  label: 'Re-parse',       method: 'parse_and_preview' },
    { id: 'discard',  label: 'Discard',        danger: true, deletes: true,
      confirmText: 'Discard this run? This permanently deletes it and its parsed rows.' },
    { id: 'validate', label: 'Validate',       method: 'validate_import' },
    { id: 'arm',      label: 'Ready to Import', primary: true, method: 'arm_import',
      confirmText: 'Arm this import for posting? You still confirm at Queue.' },
  ],
  Validated: [
    { id: 'validate', label: 'Re-validate',    method: 'validate_import' },
    { id: 'queue',    label: 'Queue',          primary: true,  method: 'queue_run',
      confirmText: 'Queue this import? Posting will start.' },
  ],
  Queued: [
    { id: 'cancel',   label: 'Cancel',       danger: true,   method: 'cancel_run',
      confirmText: 'Cancel this queued run?' },
  ],
  Processing: [
    { id: 'cancel',   label: 'Cancel',       danger: true,   method: 'cancel_run',
      confirmText: 'Cancel processing? Already-posted rows stay posted.' },
  ],
  Completed: [
    { id: 'revert',   label: 'Revert',       danger: true,   method: 'revert_run',
      confirmText: 'Revert all posted documents from this import?' },
  ],
  Failed: [
    { id: 'validate', label: 'Re-validate',  method: 'validate_import' },
  ],
  Cancelled: [
    { id: 'validate', label: 'Re-validate',  method: 'validate_import' },
  ],
  Reverted: [
    { id: 'queue',    label: 'Re-queue',     method: 'queue_run' },
  ],
};

const actions = computed(() => RUN_ACTIONS[status.value] || []);

const rowsFailed = computed(() => Number(props.doc?.rows_failed || 0));

// Arming ("Ready to Import") and Queue both commit toward posting; the backend
// refuses while any row is in error (RUN_BLOCKED_BY_ROW_ERRORS). Surface that
// block here so the button reads as disabled instead of erroring on click —
// every errored row must be fixed first (all-or-nothing). Validate itself is
// never blocked: it is a pure check that reports the errors.
function isBlocked(action) {
  return ['queue_run', 'arm_import'].includes(action.method) && rowsFailed.value > 0;
}

async function runAction(action) {
  if (!props.runName || busy.value || isBlocked(action)) return;
  if (action.confirmText) {
    const ok = await openConfirm({
      title: action.label,
      body: action.confirmText,
      kind: action.danger ? 'danger' : 'warning',
      confirmLabel: action.label,
    });
    if (!ok) return;
  }
  busy.value = action.id;
  try {
    // Discard deletes the run outright, then leaves the workspace.
    if (action.deletes) {
      await frappeRequest({
        url: 'frappe.client.delete',
        method: 'POST',
        params: { doctype: 'Cashew Import Run', name: props.runName },
      });
      toast.success('Run discarded.');
      router.push('/runs');
      return;
    }
    await frappeRequest({
      url: `cashew_integration.api.${action.method}`,
      method: 'POST',
      params: { run_name: props.runName },
    });
    emit('reload');
    toast.success(`${action.label} done`);
  } catch (_e) {
    /* interceptor toasted */
  } finally {
    busy.value = null;
  }
}

function openConfirm({ title, body, confirmLabel, kind }) {
  return new Promise((resolve) => {
    confirmState.value = { open: true, title, body, confirmLabel, kind, resolve };
  });
}
function resolveConfirm(answer) {
  const s = confirmState.value;
  confirmState.value = null;
  s?.resolve(answer);
}

function goBack() { router.push('/runs'); }
function openInDesk() {
  if (!props.runName) return;
  window.open(`/app/cashew-import-run/${props.runName}`, '_blank');
}
</script>

<template>
  <header class="border-b border-gray-200 bg-white sticky top-0 z-20">
    <div class="px-4 py-2 flex items-center gap-3">
      <button
        type="button"
        class="h-8 w-8 rounded-md hover:bg-gray-100 flex items-center justify-center text-gray-600"
        aria-label="Back to imports"
        @click="goBack"
      >
        <ChevronLeft :size="18" />
      </button>
      <span class="font-mono text-sm text-gray-800 truncate min-w-0">
        {{ runName || '(new import)' }}
      </span>
      <StatusPill v-if="status" kind="run-status" :value="status" />
      <StatusPill v-if="doc?.source_type" kind="source-type" :value="doc.source_type" size="sm" />
      <span
        v-if="inFlight"
        class="inline-flex items-center gap-1 text-[11px] text-gray-600"
        :title="status === 'Reverting' ? 'Reverting…' : 'Import in progress'"
      >
        <Loader2 :size="12" class="animate-spin" />
        <span>{{ status === 'Reverting' ? 'Reverting…' : 'Working…' }}</span>
      </span>
      <span
        v-if="realtimeStatus === 'connected'"
        class="inline-flex items-center gap-1 text-[11px] text-green-700"
        title="Live updates connected"
      >
        <Radio :size="11" class="animate-pulse" /> Live
      </span>
      <span class="flex-1" />
      <button
        v-if="runName"
        type="button"
        class="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-800"
        @click="openInDesk"
      >
        Open in Desk <ExternalLink :size="12" />
      </button>
    </div>

    <div class="px-4 py-2 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-gray-100">
      <div class="text-xs text-gray-600 truncate min-w-0 flex-1">
        <template v-if="doc">
          <span v-if="doc.company">{{ doc.company }}</span>
          <template v-if="periodFmt"><span> · </span>{{ periodFmt }}</template>
          <template v-if="doc.rows_total"><span> · </span>{{ doc.rows_total }} rows</template>
          <template v-if="doc.rows_valid"><span> · </span><span class="text-green-700">{{ doc.rows_valid }} valid</span></template>
          <template v-if="doc.rows_failed"><span> · </span><span class="text-red-700">{{ doc.rows_failed }} failed</span></template>
          <template v-if="doc.rows_posted"><span> · </span><span class="text-green-700">{{ doc.rows_posted }} posted</span></template>
        </template>
      </div>
      <div class="flex items-center gap-2">
        <span v-if="rowsFailed > 0" class="text-xs text-red-700">
          Fix {{ rowsFailed }} errored row{{ rowsFailed === 1 ? '' : 's' }} before importing.
        </span>
        <Button
          v-for="a in actions"
          :key="a.id"
          :variant="a.primary ? 'solid' : 'subtle'"
          :theme="a.danger ? 'red' : (a.primary ? 'gray' : 'gray')"
          :loading="busy === a.id"
          :disabled="!!busy || isBlocked(a)"
          :title="isBlocked(a) ? 'Import is blocked until every errored row is fixed.' : undefined"
          @click="runAction(a)"
        >
          {{ a.label }}
        </Button>
      </div>
    </div>

    <ConfirmDialog
      v-if="confirmState"
      :open="confirmState.open"
      :title="confirmState.title"
      :body="confirmState.body"
      :confirm-label="confirmState.confirmLabel"
      :kind="confirmState.kind"
      @update:open="(v) => { if (!v) resolveConfirm(false); }"
      @confirm="resolveConfirm(true)"
      @cancel="resolveConfirm(false)"
    />
  </header>
</template>
