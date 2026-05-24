<script setup>
import { ref, watchEffect, onMounted } from 'vue';
import { Autocomplete } from 'frappe-ui';
import { createResource } from 'frappe-ui';

const props = defineProps({ modelValue: { type: String, default: null } });
const emit = defineEmits(['update:modelValue', 'visible']);

const companies = ref([]);
const value = ref(props.modelValue);

watchEffect(() => { value.value = props.modelValue; });

const companyResource = createResource({
  url: 'frappe.client.get_list',
  makeParams: () => ({
    doctype: 'Company',
    fields: ['name'],
    limit_page_length: 50,
    order_by: 'name asc',
  }),
  onSuccess: (rows) => {
    companies.value = (rows || []).map((r) => ({ value: r.name, label: r.name }));
    emit('visible', companies.value.length > 1);
  },
});

onMounted(() => companyResource.reload());

function onUpdate(v) {
  const next = v?.value || v?.name || v || null;
  emit('update:modelValue', next || null);
}
</script>

<template>
  <Autocomplete
    v-if="companies.length > 1"
    :modelValue="value"
    :options="companies"
    placeholder="All companies"
    @update:modelValue="onUpdate"
  />
</template>
