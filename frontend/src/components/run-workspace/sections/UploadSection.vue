<script setup>
import { reactive, ref, computed } from 'vue';
import { Button, Input, toast, frappeRequest } from 'frappe-ui';

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
  company: props.doc?.company || settings.default_company || sysDefaults.default_company || null,
  source_file: props.doc?.source_file || null,
  balance_adjustment_account: props.doc?.balance_adjustment_account || null,
  je_rounding_tolerance: props.doc?.je_rounding_tolerance ?? 0.01,
  // f011 c005 — SQLite ingestion path. Default CSV = today's flow, purely additive.
  source_type: props.doc?.source_type || 'CSV',
  import_from_date: props.doc?.import_from_date || null,
  import_to_date: props.doc?.import_to_date || null,
});

const busy = ref(null);

const isSqlite = computed(() => form.source_type === 'SQLite');

// Fail-early UX mirror of the c002 server guard (read_sqlite throws SQL_DATE_WINDOW_INVALID);
// the server stays authoritative — this only disables Parse before the round-trip.
const dateWindowInvalid = computed(
  () => isSqlite.value && !!form.import_from_date && !!form.import_to_date
    && form.import_from_date > form.import_to_date,
);

const canParse = computed(() => !!form.company && !!form.source_file && !dateWindowInvalid.value);

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
        source_type: form.source_type,
        // send null (not undefined) so a blank window clears cleanly; CSV ignores them
        import_from_date: isSqlite.value ? (form.import_from_date || null) : null,
        import_to_date: isSqlite.value ? (form.import_to_date || null) : null,
      },
    },
  });
  return res?.name;
}

async function persistFieldChanges(newName) {
  if (!props.runName || !props.doc) return;
  const patches = [];
  for (const field of ['company', 'source_file', 'balance_adjustment_account', 'je_rounding_tolerance', 'source_type', 'import_from_date', 'import_to_date']) {
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
    toast.success('Parsed.');
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
        <p class="text-sm text-gray-500 mt-1">
          Pick a company and upload the
          {{ isSqlite ? 'Cashew SQLite backup (.sql)' : 'Cashew CSV export' }}.
        </p>
      </header>

      <div>
        <label class="text-sm font-medium text-gray-700 block mb-1">Company</label>
        <CompanyPicker v-model="form.company" />
      </div>

      <div>
        <label class="text-sm font-medium text-gray-700 block mb-1">Source</label>
        <div class="inline-flex gap-1 rounded-lg border border-gray-200 p-0.5 bg-gray-50">
          <Button
            v-for="opt in ['CSV', 'SQLite']"
            :key="opt"
            :variant="form.source_type === opt ? 'solid' : 'subtle'"
            theme="gray"
            @click="form.source_type = opt"
          >
            {{ opt }}
          </Button>
        </div>
      </div>

      <div v-if="isSqlite" class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">From date (optional)</label>
          <Input type="date" :modelValue="form.import_from_date || ''"
            @update:modelValue="(v) => (form.import_from_date = v || null)" />
        </div>
        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">To date (optional)</label>
          <Input type="date" :modelValue="form.import_to_date || ''"
            @update:modelValue="(v) => (form.import_to_date = v || null)" />
        </div>
        <p class="text-xs text-gray-500 sm:col-span-2">Blank = import whole backup.</p>
        <p v-if="dateWindowInvalid" class="text-xs text-red-600 sm:col-span-2">
          "From" date is after "To" date.
        </p>
      </div>

      <div>
        <label class="text-sm font-medium text-gray-700 block mb-1">Source file</label>
        <CsvDropzone v-model="form.source_file" :source-type="form.source_type" />
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
