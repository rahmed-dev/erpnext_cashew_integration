<script setup>
import { computed } from 'vue';
import { Link } from 'frappe-ui/frappe';

const props = defineProps({
  modelValue: { type: [String, null], default: null },
});
const emit = defineEmits(['update:modelValue']);

const value = computed({
  get: () => props.modelValue || '',
  set: (v) => emit('update:modelValue', v || null),
});
</script>

<template>
  <Link v-model="value" doctype="Company" placeholder="Company" />
</template>
