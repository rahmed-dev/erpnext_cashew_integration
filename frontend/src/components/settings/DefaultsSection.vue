<script setup>
import { computed } from 'vue';
import { Link } from 'frappe-ui/frappe';

const props = defineProps({
  company: { type: [String, null], default: null },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['update:company']);

const value = computed({
  get: () => props.company || '',
  set: (v) => emit('update:company', v || null),
});
</script>

<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5">
    <header class="mb-4">
      <h2 class="text-base font-semibold text-gray-900">Defaults</h2>
      <p class="text-sm text-gray-500 mt-1">Pre-selected values for new imports.</p>
    </header>

    <div>
      <label class="text-sm font-medium text-gray-700 block mb-1">Default Company</label>
      <Link
        v-model="value"
        doctype="Company"
        placeholder="Select a Company"
        :disabled="disabled"
      />
      <p class="text-xs text-gray-500 mt-1">Pre-selected when creating a new import.</p>
    </div>
  </section>
</template>
