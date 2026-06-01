<script setup>
import { ref, reactive, nextTick } from 'vue';
import { Spinner, frappeRequest, toast } from 'frappe-ui';
import LinkField from '@/components/shared/LinkField.vue';

const props = defineProps({
  row: { type: Object, required: true },
  runName: { type: String, required: true },
  editable: { type: Boolean, default: true },
});
const emit = defineEmits(['saved']);

const editing = ref(false);
const saving = ref(false);
const typeRef = ref(null);
const local = reactive({ party_type: '', party: '' });

function activate() {
  if (!props.editable || saving.value) return;
  local.party_type = props.row.resolved_party_type || '';
  local.party = props.row.resolved_party || '';
  editing.value = true;
  nextTick(() => typeRef.value?.focus?.());
}

function cancel() {
  editing.value = false;
  local.party_type = '';
  local.party = '';
}

async function save() {
  if (saving.value) return;
  saving.value = true;
  try {
    await frappeRequest({
      url: 'cashew_integration.api.row_explorer_set_party',
      method: 'POST',
      params: {
        run_name: props.runName,
        row_indices: [props.row.row_idx],
        party_type: local.party_type || null,
        party: local.party || null,
      },
    });
    emit('saved');
    cancel();
  } catch (_e) { /* interceptor toasted */ }
  finally { saving.value = false; }
}
</script>

<template>
  <div v-if="!editing" class="cursor-pointer min-w-0" @dblclick="activate">
    <span v-if="row.resolved_party" class="text-sm truncate" :title="row.resolved_party">
      {{ row.resolved_party }}
      <span class="text-xs text-gray-500">({{ row.resolved_party_type }})</span>
    </span>
    <span v-else-if="row.requires_party" class="text-xs text-red-700">Set party</span>
    <span v-else class="text-gray-400">—</span>
  </div>
  <div v-else class="flex items-center gap-1">
    <select
      ref="typeRef"
      v-model="local.party_type"
      class="text-xs border border-gray-300 rounded px-1 py-0.5 bg-white"
      @keydown.enter.prevent="save"
      @keydown.esc.prevent="cancel"
    >
      <option value="">None</option>
      <option value="Customer">Customer</option>
      <option value="Supplier">Supplier</option>
    </select>
    <LinkField
      v-if="local.party_type"
      :modelValue="local.party"
      :doctype="local.party_type"
      class="text-xs flex-1 min-w-0"
      placeholder="Search party"
      @update:modelValue="(v) => (local.party = v)"
      @keydown.enter.prevent="save"
      @keydown.esc.prevent="cancel"
    />
    <Spinner v-if="saving" class="w-3 h-3" />
  </div>
</template>
