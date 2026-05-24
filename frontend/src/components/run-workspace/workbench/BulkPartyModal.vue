<script setup>
import { ref, reactive } from 'vue';
import { Dialog, Button, Autocomplete, frappeRequest, toast } from 'frappe-ui';

const props = defineProps({
  open: { type: Boolean, default: false },
  runName: { type: String, required: true },
  selectedRows: { type: Array, default: () => [] },
});
const emit = defineEmits(['update:open', 'saved']);

const form = reactive({ party_type: '', party: '' });
const saving = ref(false);

function reset() { form.party_type = ''; form.party = ''; }
function close() { emit('update:open', false); }

async function save() {
  if (!props.selectedRows.length || saving.value) return;
  saving.value = true;
  try {
    await frappeRequest({
      url: 'cashew_integration.api.row_explorer_set_party',
      method: 'POST',
      params: {
        run_name: props.runName,
        row_indices: props.selectedRows.map((r) => r.row_idx),
        party_type: form.party_type || null,
        party: form.party || null,
      },
    });
    toast.success(`Set party on ${props.selectedRows.length} row${props.selectedRows.length === 1 ? '' : 's'}.`);
    emit('saved');
    reset();
    close();
  } catch (_e) { /* interceptor toasted */ }
  finally { saving.value = false; }
}

function onPartySelect(opt) { form.party = opt?.value ?? opt?.name ?? ''; }
</script>

<template>
  <Dialog :modelValue="open" @update:modelValue="(v) => emit('update:open', v)">
    <template #body>
      <div class="p-5 space-y-3">
        <h2 class="text-base font-semibold">Set party on {{ selectedRows.length }} row{{ selectedRows.length === 1 ? '' : 's' }}</h2>
        <p class="text-xs text-gray-500">Choose the party type and value. Existing party values on selected rows are overwritten.</p>

        <div>
          <label class="text-xs font-medium text-gray-700 block mb-1">Party type</label>
          <select v-model="form.party_type" class="text-sm border border-gray-300 rounded px-2 py-1 bg-white w-full">
            <option value="">None</option>
            <option value="Customer">Customer</option>
            <option value="Supplier">Supplier</option>
          </select>
        </div>
        <div v-if="form.party_type">
          <label class="text-xs font-medium text-gray-700 block mb-1">Party</label>
          <Autocomplete
            :modelValue="form.party"
            :options="[]"
            :reference_doctype="form.party_type"
            @update:modelValue="onPartySelect"
          />
        </div>

        <div class="flex justify-end gap-2 pt-2">
          <Button variant="ghost" @click="close">Cancel</Button>
          <Button variant="solid" theme="gray" :loading="saving" :disabled="saving" @click="save">Save</Button>
        </div>
      </div>
    </template>
  </Dialog>
</template>
