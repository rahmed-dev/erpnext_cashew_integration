<script setup>
import { Landmark, ChevronDown, ArrowLeftRight } from 'lucide-vue-next';
import { Dropdown } from 'frappe-ui';

function backToDesk() {
  window.location.href = '/app';
}
</script>

<template>
  <Dropdown
    placement="bottom-start"
    :options="[
      { label: 'Back to Desk', icon: 'arrow-left', onClick: backToDesk },
    ]"
  >
    <template #default="{ open }">
      <button
        type="button"
        class="w-full flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-gray-50 text-left"
        :aria-expanded="open"
      >
        <span class="h-7 w-7 rounded-md bg-cs-accent-50 text-cs-accent flex items-center justify-center shrink-0">
          <Landmark :size="16" />
        </span>
        <span class="flex-1 min-w-0">
          <span class="block text-sm font-semibold leading-tight truncate">Cashew</span>
        </span>
        <ChevronDown :size="14" class="text-gray-400" />
      </button>
    </template>
  </Dropdown>
</template>
