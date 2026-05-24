<script setup>
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { Button, toast, frappeRequest } from 'frappe-ui';
import { ChevronLeft, ExternalLink, Radio } from 'lucide-vue-next';

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
const periodFmt = computed(() => formatRange(props.doc?.period_start, props.doc?.period_end));

const RUN_ACTIONS = {
  Draft: [
    { id: 'parse',   label: 'Parse',         primary: true,  method: 'parse_and_preview' },
  ],
  Parsed: [
    { id: 'validate', label: 'Validate',     primary: true,  method: 'validate_import' },
  ],
  Validated: [
    { id: 'queue',    label: 'Queue',        primary: true,  method: 'queue_run',
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

async function runAction(action) {
  if (!props.runName || busy.value) return;
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
        <Button
          v-for="a in actions"
          :key="a.id"
          :variant="a.primary ? 'solid' : 'subtle'"
          :theme="a.danger ? 'red' : (a.primary ? 'gray' : 'gray')"
          :loading="busy === a.id"
          :disabled="!!busy"
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
