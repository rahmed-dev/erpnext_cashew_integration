<script setup>
import { BarChart3, Plus } from 'lucide-vue-next';
import { Button } from 'frappe-ui';

defineEmits(['new-import']);

function focusPeriod() {
  document.querySelector('[data-period-selector]')?.focus();
}
</script>

<template>
  <div class="rounded-lg border border-dashed border-gray-300 bg-white py-16 px-6 flex flex-col items-center text-center mt-6">
    <span class="w-12 h-12 rounded-full bg-[var(--cs-accent-50)] text-[var(--cs-accent)] flex items-center justify-center mb-3">
      <BarChart3 :size="22" />
    </span>
    <h3 class="text-base font-semibold text-gray-900">No activity in this period</h3>
    <p class="text-sm text-gray-500 mt-1 max-w-md">
      Start an import to see income, expense, balances, and category breakdowns here.
    </p>
    <div class="mt-4 flex items-center gap-3">
      <Button variant="solid" theme="gray" :icon-left="Plus" @click="$emit('new-import')">
        Start an Import
      </Button>
      <button class="text-sm text-[var(--cs-accent)] hover:underline" @click="focusPeriod">Change period</button>
    </div>
  </div>
</template>
