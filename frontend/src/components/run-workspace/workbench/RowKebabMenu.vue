<script setup>
import { computed } from 'vue';
import { Dropdown } from 'frappe-ui';
import { MoreVertical } from 'lucide-vue-next';

const props = defineProps({
  row: { type: Object, required: true },
  editable: { type: Boolean, default: true },
});
const emit = defineEmits(['action']);

const options = computed(() => {
  const items = [];
  if (props.row.validation_status === 'Error' && props.editable) {
    items.push({ label: 'Fix this row…', onClick: () => emit('action', { action: 'fix', row: props.row }) });
  }
  if (props.editable) {
    items.push({ label: 'Re-validate row', onClick: () => emit('action', { action: 'revalidate', row: props.row }) });
  }
  items.push({ label: 'View row JSON', onClick: () => emit('action', { action: 'view-json', row: props.row }) });
  if (props.row.posted_docname) {
    items.push({ label: 'Open posted doc', onClick: () => emit('action', { action: 'open-posted', row: props.row }) });
  }
  return items;
});
</script>

<template>
  <Dropdown :options="options" placement="left">
    <template #default>
      <button
        type="button"
        class="h-7 w-7 rounded hover:bg-gray-100 inline-flex items-center justify-center text-gray-500"
        aria-label="Row actions"
        @click.stop
      >
        <MoreVertical :size="14" />
      </button>
    </template>
  </Dropdown>
</template>
