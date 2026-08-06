<script setup>
import CategoryBreakdownList from './CategoryBreakdownList.vue';

defineProps({
  incomeBy: { type: Array, default: () => [] },
  expenseBy: { type: Array, default: () => [] },
  currency: { type: String, default: 'PKR' },
});
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-4">
    <header class="mb-3">
      <h3 class="text-sm font-semibold text-gray-900">Top accounts</h3>
      <p class="text-xs text-gray-500">From Chart of Accounts · up to 10 each</p>
    </header>
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-5">
      <CategoryBreakdownList
        title="Income"
        :items="incomeBy"
        :currency="currency"
        tone="pos"
      />
      <CategoryBreakdownList
        title="Expense"
        :items="expenseBy"
        :currency="currency"
        tone="neg"
      />
    </div>
  </div>
</template>
