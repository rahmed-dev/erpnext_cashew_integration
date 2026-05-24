<script setup>
import { ref } from 'vue';
import { Button, toast, frappeRequest } from 'frappe-ui';
import ParseStatsBar from '@/components/run-workspace/preview/ParseStatsBar.vue';
import PreviewTable from '@/components/run-workspace/preview/PreviewTable.vue';
import ConfirmDialog from '@/components/shared/ConfirmDialog.vue';
import { SPA_BASE } from '@/router';

const props = defineProps({
  doc: { type: Object, required: true },
  rows: { type: Array, default: () => [] },
  runName: { type: [String, null], default: null },
});
const emit = defineEmits(['reload']);

const busy = ref(null);
const confirmState = ref(null);

async function call(method) {
  busy.value = method;
  try {
    await frappeRequest({
      url: `cashew_integration.api.${method}`,
      method: 'POST',
      params: { run_name: props.runName },
    });
    emit('reload');
  } catch (_e) { /* interceptor toasted */ }
  finally { busy.value = null; }
}

async function onReparse() { call('parse_and_preview'); }
async function onValidate() { call('validate_import'); }

async function onDiscard() {
  const ok = await new Promise((resolve) => {
    confirmState.value = { open: true, resolve };
  });
  if (!ok) return;
  busy.value = 'discard';
  try {
    await frappeRequest({
      url: 'frappe.client.delete',
      method: 'POST',
      params: { doctype: 'Cashew Import Run', name: props.runName },
    });
    toast.success('Draft discarded.');
    window.location.assign(`${SPA_BASE}/runs`);
  } catch (_e) { /* interceptor toasted */ }
  finally { busy.value = null; }
}

function resolveConfirm(answer) {
  const s = confirmState.value;
  confirmState.value = null;
  s?.resolve(answer);
}
</script>

<template>
  <div class="space-y-4">
    <ParseStatsBar :doc="doc" :rows="rows" />
    <PreviewTable :rows="rows" :currency="doc?.company_currency || 'PKR'" />
    <div class="flex flex-wrap items-center justify-end gap-2">
      <Button variant="ghost" :loading="busy === 'parse_and_preview'" :disabled="!!busy" @click="onReparse">Re-parse</Button>
      <Button variant="ghost" theme="red" :loading="busy === 'discard'" :disabled="!!busy" @click="onDiscard">Discard</Button>
      <Button variant="solid" theme="gray" :loading="busy === 'validate_import'" :disabled="!!busy" @click="onValidate">Validate →</Button>
    </div>

    <ConfirmDialog
      v-if="confirmState"
      :open="confirmState.open"
      title="Discard draft?"
      body="This permanently deletes the run record and its parsed rows."
      kind="danger"
      confirm-label="Discard"
      cancel-label="Keep"
      @update:open="(v) => { if (!v) resolveConfirm(false); }"
      @confirm="resolveConfirm(true)"
      @cancel="resolveConfirm(false)"
    />
  </div>
</template>
