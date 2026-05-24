<script setup>
import { computed } from 'vue';
import KebabMenu from '@/components/shared/KebabMenu.vue';

const props = defineProps({ row: { type: Object, required: true } });
const emit = defineEmits(['action']);

const items = computed(() => {
  const r = props.row;
  const out = [];
  out.push({ label: 'Open', action: () => emit('action', { type: 'open', row: r }) });
  if (r.diagnostics_file) {
    out.push({ label: 'Download diagnostics', action: () => emit('action', { type: 'diagnostics', row: r }) });
  }
  if (r.status === 'Completed') {
    out.push({ label: 'Revert', danger: true, action: () => emit('action', { type: 'revert', row: r }) });
  }
  if (r.status === 'Queued' || r.status === 'Processing') {
    out.push({ label: 'Cancel run', danger: true, action: () => emit('action', { type: 'cancel', row: r }) });
  }
  return out;
});
</script>

<template>
  <KebabMenu :items="items" align="right" @click.stop />
</template>
