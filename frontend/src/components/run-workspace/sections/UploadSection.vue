<script setup>
import { reactive, ref, computed } from 'vue';
import { Button, toast, frappeRequest } from 'frappe-ui';

import CompanyPicker from '@/components/run-workspace/upload/CompanyPicker.vue';
import CsvDropzone from '@/components/run-workspace/upload/CsvDropzone.vue';
import OptionalConfigDisclosure from '@/components/run-workspace/upload/OptionalConfigDisclosure.vue';

import { useCashewSettings, useSysDefaults } from '@/boot';

const props = defineProps({
  doc: { type: [Object, null], default: null },
  runName: { type: [String, null], default: null },
});
const emit = defineEmits(['reload', 'parsed']);

const settings = useCashewSettings();
const sysDefaults = useSysDefaults();

const form = reactive({
  company: props.doc?.company || settings.company || sysDefaults.company || null,
  source_file: props.doc?.source_file || null,
  balance_adjustment_account: props.doc?.balance_adjustment_account || null,
  je_rounding_tolerance: props.doc?.je_rounding_tolerance ?? 0.01,
});

const busy = ref(null);

const canParse = computed(() => !!form.company && !!form.source_file);

async function ensureRunExists() {
  if (props.runName) return props.runName;
  const res = await frappeRequest({
    url: 'frappe.client.insert',
    method: 'POST',
    params: {
      doc: {
        doctype: 'Cashew Import Run',
        company: form.company,
        source_file: form.source_file,
        balance_adjustment_account: form.balance_adjustment_account || null,
        je_rounding_tolerance: form.je_rounding_tolerance,
      },
    },
  });
  return res?.name;
}

async function persistFieldChanges(newName) {
  if (!props.runName || !props.doc) return;
  const patches = [];
  for (const field of ['company', 'source_file', 'balance_adjustment_account', 'je_rounding_tolerance']) {
    if ((form[field] ?? '') !== (props.doc[field] ?? '')) {
      patches.push(frappeRequest({
        url: 'frappe.client.set_value',
        method: 'POST',
        params: {
          doctype: 'Cashew Import Run',
          name: newName,
          fieldname: field,
          value: form[field] ?? '',
        },
      }));
    }
  }
  if (patches.length) await Promise.all(patches);
}

async function onParse() {
  if (!canParse.value || busy.value) return;
  busy.value = 'parse';
  try {
    let name = props.runName;
    if (!name) {
      name = await ensureRunExists();
      if (!name) throw new Error('Could not create Cashew Import Run');
    } else {
      await persistFieldChanges(name);
    }
    await frappeRequest({
      url: 'cashew_integration.api.parse_and_preview',
      method: 'POST',
      params: { run_name: name },
    });
    toast.success('CSV parsed.');
    if (!props.runName) emit('parsed', name);
    else emit('reload');
  } catch (_e) {
    /* interceptor toasted */
  } finally {
    busy.value = null;
  }
}
</script>

<template>
  <div class="space-y-4 max-w-2xl">
    <section class="rounded-lg border border-gray-200 bg-white p-5 space-y-4">
      <header>
        <h2 class="text-base font-semibold text-gray-900">New Import</h2>
        <p class="text-sm text-gray-500 mt-1">Pick a company and upload the Cashew CSV export.</p>
      </header>

      <div>
        <label class="text-sm font-medium text-gray-700 block mb-1">Company</label>
        <CompanyPicker v-model="form.company" />
      </div>

      <div>
        <label class="text-sm font-medium text-gray-700 block mb-1">Source file</label>
        <CsvDropzone v-model="form.source_file" />
      </div>

      <OptionalConfigDisclosure
        v-model:balance-adjustment-account="form.balance_adjustment_account"
        v-model:je-rounding-tolerance="form.je_rounding_tolerance"
      />
    </section>

    <div class="flex justify-end">
      <Button
        variant="solid"
        theme="gray"
        :disabled="!canParse || !!busy"
        :loading="busy === 'parse'"
        @click="onParse"
      >
        Parse →
      </Button>
    </div>
  </div>
</template>
