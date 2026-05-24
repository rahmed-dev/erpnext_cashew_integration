<script setup>
import { ref, computed } from 'vue';
import { Button, frappeRequest, toast } from 'frappe-ui';
import { ExternalLink } from 'lucide-vue-next';
import ConfirmDialog from '@/components/shared/ConfirmDialog.vue';

const props = defineProps({
  doc: { type: Object, required: true },
});
const emit = defineEmits(['reload']);

const busy = ref(null);
const confirmState = ref(null);

const status = computed(() => props.doc?.status);

async function call(method, opts = {}) {
  if (opts.confirmText) {
    const ok = await new Promise((resolve) => {
      confirmState.value = {
        open: true,
        title: opts.confirmTitle || 'Confirm',
        body: opts.confirmText,
        confirmLabel: opts.confirmLabel || 'Confirm',
        kind: opts.kind || 'warning',
        resolve,
      };
    });
    if (!ok) return;
  }
  busy.value = method;
  try {
    await frappeRequest({
      url: `cashew_integration.api.${method}`,
      method: 'POST',
      params: { run_name: props.doc?.name },
    });
    emit('reload');
    toast.success(opts.successText || `${method} done`);
  } catch (_e) { /* interceptor toasted */ }
  finally { busy.value = null; }
}

function resolveConfirm(answer) {
  const s = confirmState.value;
  confirmState.value = null;
  s?.resolve(answer);
}
function openInDesk() {
  if (props.doc?.name) window.open(`/app/cashew-import-run/${props.doc.name}`, '_blank');
}
</script>

<template>
  <div class="rounded-lg border border-red-200 bg-red-50/40 p-4">
    <h3 class="text-sm font-semibold text-red-900 mb-2">More actions</h3>

    <div class="flex flex-wrap items-center gap-2">
      <template v-if="status === 'Completed'">
        <Button
          variant="solid"
          theme="red"
          :loading="busy === 'revert_run'"
          :disabled="!!busy"
          @click="call('revert_run', { confirmText: 'Revert all posted documents from this import?', confirmTitle: 'Revert import', confirmLabel: 'Revert', kind: 'danger', successText: 'Revert started.' })"
        >
          Revert this import
        </Button>
      </template>

      <template v-if="['Failed'].includes(status)">
        <Button variant="subtle" theme="gray" :loading="busy === 'validate_import'" :disabled="!!busy" @click="call('validate_import')">
          Re-validate
        </Button>
        <Button variant="subtle" theme="gray" :loading="busy === 'queue_run'" :disabled="!!busy" @click="call('queue_run', { confirmText: 'Re-queue this import?', confirmLabel: 'Queue' })">
          Re-queue
        </Button>
      </template>

      <template v-if="status === 'Cancelled'">
        <Button variant="subtle" theme="gray" :loading="busy === 'queue_run'" :disabled="!!busy" @click="call('queue_run', { confirmText: 'Re-queue this import?', confirmLabel: 'Queue' })">
          Re-queue
        </Button>
      </template>

      <template v-if="status === 'Reverted'">
        <Button variant="subtle" theme="gray" :loading="busy === 'queue_run'" :disabled="!!busy" @click="call('queue_run', { confirmText: 'Re-queue this import?', confirmLabel: 'Queue' })">
          Re-queue
        </Button>
      </template>

      <template v-if="status === 'Revert-Failed'">
        <Button variant="solid" theme="red" :loading="busy === 'revert_run'" :disabled="!!busy" @click="call('revert_run', { confirmText: 'Retry the revert?', confirmLabel: 'Retry', kind: 'danger' })">
          Retry revert
        </Button>
      </template>

      <button
        type="button"
        class="inline-flex items-center gap-1 text-xs text-gray-600 hover:text-gray-900 ml-auto"
        @click="openInDesk"
      >
        Open in Desk <ExternalLink :size="12" />
      </button>
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
  </div>
</template>
