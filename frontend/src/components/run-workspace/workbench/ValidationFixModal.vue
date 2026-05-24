<script setup>
import { reactive, ref, computed, watch } from 'vue';
import { Dialog, Button, Autocomplete, frappeRequest } from 'frappe-ui';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';

const props = defineProps({
  row: { type: [Object, null], default: null },
  runName: { type: String, required: true },
  open: { type: Boolean, default: false },
});
const emit = defineEmits(['update:open', 'saved']);

const SHOW_BY_CODE = {
  NO_ACCOUNT_MAP:   { account: true },
  NO_EXTERNAL_ACCT: { external: true },
  MISSING_PARTY:    { party: true },
};

const flags = computed(() => SHOW_BY_CODE[props.row?.validation_error_code]
  || { account: true, external: true, party: true });

const form = reactive({
  account: '', external_account: '', party_type: '', party: '',
});

watch(() => props.row, (r) => {
  if (!r) return;
  form.account = r.resolved_account || '';
  form.external_account = r.resolved_external_account || '';
  form.party_type = r.resolved_party_type || '';
  form.party = r.resolved_party || '';
}, { immediate: true });

const saving = ref(false);

function close() { emit('update:open', false); }

async function save() {
  if (!props.row || saving.value) return;
  saving.value = true;
  try {
    const writes = [];
    if (flags.value.party) {
      writes.push(frappeRequest({
        url: 'cashew_integration.api.row_explorer_set_party',
        method: 'POST',
        params: {
          run_name: props.runName,
          row_indices: [props.row.row_idx],
          party_type: form.party_type || null,
          party: form.party || null,
        },
      }));
    }
    if (writes.length) await Promise.all(writes);
    await frappeRequest({
      url: 'cashew_integration.api.row_explorer_revalidate',
      method: 'POST',
      params: { run_name: props.runName, row_indices: [props.row.row_idx] },
    });
    emit('saved');
    close();
  } catch (_e) { /* interceptor toasted */ }
  finally { saving.value = false; }
}

function onPartySelect(opt) { form.party = opt?.value ?? opt?.name ?? ''; }
function onAccountSelect(opt) { form.account = opt?.value ?? opt?.name ?? ''; }
function onExtSelect(opt) { form.external_account = opt?.value ?? opt?.name ?? ''; }
</script>

<template>
  <Dialog :modelValue="open" @update:modelValue="(v) => emit('update:open', v)">
    <template #body>
      <div v-if="row" class="p-5 space-y-3">
        <h2 class="text-base font-semibold">Fix row #{{ row.row_idx }}</h2>

        <div class="rounded bg-red-50 border border-red-100 p-2">
          <div class="text-xs font-semibold text-red-700">{{ row.validation_error_code || 'Error' }}</div>
          <div class="text-xs text-red-700">{{ row.validation_error_message || '—' }}</div>
        </div>

        <dl class="grid grid-cols-2 gap-y-1 text-sm">
          <dt class="text-gray-500">Date</dt><dd>{{ row.txn_date || '—' }}</dd>
          <dt class="text-gray-500">Account</dt><dd>{{ row.raw_account || '—' }}</dd>
          <dt class="text-gray-500">Amount</dt>
          <dd><AmountDisplay :amount="row.base_amount" :currency="row.company_currency || 'PKR'" :signed="true" /></dd>
          <dt class="text-gray-500">Type</dt><dd>{{ row.txn_type || '—' }}</dd>
          <dt class="text-gray-500">Category</dt><dd>{{ row.category || '—' }}</dd>
        </dl>

        <div v-if="flags.account">
          <label class="text-xs font-medium text-gray-700 block mb-1">GL Account</label>
          <Autocomplete
            :modelValue="form.account"
            :options="[]"
            reference_doctype="Account"
            placeholder="Account"
            @update:modelValue="onAccountSelect"
          />
        </div>

        <div v-if="flags.external">
          <label class="text-xs font-medium text-gray-700 block mb-1">External Account</label>
          <Autocomplete
            :modelValue="form.external_account"
            :options="[]"
            reference_doctype="Account"
            placeholder="External Account"
            @update:modelValue="onExtSelect"
          />
        </div>

        <div v-if="flags.party">
          <label class="text-xs font-medium text-gray-700 block mb-1">Party</label>
          <div class="flex items-center gap-2">
            <select v-model="form.party_type" class="text-sm border border-gray-300 rounded px-2 py-1 bg-white">
              <option value="">None</option>
              <option value="Customer">Customer</option>
              <option value="Supplier">Supplier</option>
            </select>
            <Autocomplete
              v-if="form.party_type"
              :modelValue="form.party"
              :options="[]"
              :reference_doctype="form.party_type"
              class="flex-1"
              @update:modelValue="onPartySelect"
            />
          </div>
        </div>

        <div class="flex justify-end gap-2 pt-2">
          <Button variant="ghost" @click="close">Cancel</Button>
          <Button variant="solid" theme="gray" :loading="saving" :disabled="saving" @click="save">Save &amp; Re-validate</Button>
        </div>
      </div>
    </template>
  </Dialog>
</template>
