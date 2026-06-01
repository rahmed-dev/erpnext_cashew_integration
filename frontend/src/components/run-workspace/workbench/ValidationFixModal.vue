<script setup>
import { reactive, ref, computed, watch } from 'vue';
import { Dialog, Button, frappeRequest } from 'frappe-ui';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';
import LinkField from '@/components/shared/LinkField.vue';

const props = defineProps({
  row: { type: [Object, null], default: null },
  runName: { type: String, required: true },
  open: { type: Boolean, default: false },
});
const emit = defineEmits(['update:open', 'saved']);

// Keyed on the REAL validation error codes emitted by importer/validation.py.
const SHOW_BY_CODE = {
  MAPPING_NOT_FOUND:               { account: true, external: true },
  GROUP_ACCOUNT:                   { account: true, external: true },
  INVALID_ACCOUNT_TYPE:            { account: true },
  CATEGORY_ACCOUNT_CLASS_MISMATCH: { account: true },
  PARTY_MISSING:                   { party: true },
  LOAN_PARTY_MISSING:              { party: true },
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
  const idx = [props.row.row_idx];
  try {
    // 1. Party first (own existence check + party-presence revalidation).
    if (flags.value.party && form.party_type && form.party) {
      await frappeRequest({
        url: 'cashew_integration.api.row_explorer_set_party',
        method: 'POST',
        params: {
          run_name: props.runName, row_indices: idx,
          party_type: form.party_type, party: form.party,
        },
      });
    }
    // 2. Account / external override → runs the AUTHORITATIVE queue-time
    //    validator (clears MAPPING_NOT_FOUND etc. only if the pick resolves it).
    //    Always called: it doubles as the final re-gate. Passing null leaves a
    //    field unchanged.
    await frappeRequest({
      url: 'cashew_integration.api.row_explorer_set_account',
      method: 'POST',
      params: {
        run_name: props.runName, row_indices: idx,
        account: form.account || null,
        external_account: form.external_account || null,
      },
    });
    emit('saved');
    close();
  } catch (_e) { /* interceptor toasted */ }
  finally { saving.value = false; }
}
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
          <template v-if="row.source_currency && row.source_currency !== (row.company_currency || 'PKR')">
            <dt class="text-gray-500">Original</dt>
            <dd><AmountDisplay :amount="row.raw_amount" :currency="row.source_currency" /></dd>
          </template>
          <dt class="text-gray-500">Type</dt><dd>{{ row.txn_type || '—' }}</dd>
          <dt class="text-gray-500">Category</dt><dd>{{ row.category || '—' }}</dd>
        </dl>

        <div v-if="flags.account">
          <label class="text-xs font-medium text-gray-700 block mb-1">GL Account</label>
          <LinkField
            :modelValue="form.account"
            doctype="Account"
            placeholder="Search account"
            @update:modelValue="(v) => (form.account = v)"
          />
          <p class="text-xs text-gray-500 mt-1">
            The income/expense ledger this row posts to — the accounting side of the
            entry, balanced against your bank/cash account.
          </p>
        </div>

        <div v-if="flags.external">
          <label class="text-xs font-medium text-gray-700 block mb-1">External Account</label>
          <LinkField
            :modelValue="form.external_account"
            doctype="Account"
            placeholder="Search account"
            @update:modelValue="(v) => (form.external_account = v)"
          />
          <p class="text-xs text-gray-500 mt-1">
            Only for external transfers: the outside account the money moved to or
            from (the counterparty leg). Leave blank for normal income/expense rows.
          </p>
        </div>

        <div v-if="flags.party">
          <label class="text-xs font-medium text-gray-700 block mb-1">Party</label>
          <div class="flex items-center gap-2">
            <select v-model="form.party_type" class="text-sm border border-gray-300 rounded px-2 py-1 bg-white">
              <option value="">None</option>
              <option value="Customer">Customer</option>
              <option value="Supplier">Supplier</option>
            </select>
            <LinkField
              v-if="form.party_type"
              :modelValue="form.party"
              :doctype="form.party_type"
              class="flex-1"
              placeholder="Search party"
              @update:modelValue="(v) => (form.party = v)"
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
