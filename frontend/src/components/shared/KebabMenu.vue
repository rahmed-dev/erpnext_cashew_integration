<script setup>
import { Dropdown } from 'frappe-ui';
import { MoreVertical } from 'lucide-vue-next';

defineProps({
  items: { type: Array, required: true }, // [{ label, icon?, action, disabled?, danger?, divider? }]
  align: { type: String, default: 'right' },
});

function normalize(items) {
  return items.filter(Boolean).map((it) => ({
    label: it.label,
    icon: it.icon,
    onClick: () => { if (!it.disabled && typeof it.action === 'function') it.action(); },
    disabled: !!it.disabled,
    isDivider: !!it.divider,
    component: undefined,
    class: it.danger ? 'text-red-600' : '',
  }));
}
</script>

<template>
  <Dropdown
    :placement="align === 'left' ? 'bottom-start' : 'bottom-end'"
    :options="normalize(items)"
  >
    <template #default="{ open }">
      <button
        type="button"
        class="h-7 w-7 rounded-md hover:bg-gray-100 flex items-center justify-center text-gray-600"
        :aria-expanded="open"
        aria-label="More actions"
        @click.stop
      >
        <MoreVertical :size="16" />
      </button>
    </template>
  </Dropdown>
</template>
