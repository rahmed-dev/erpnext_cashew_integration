<script setup>
import DeskLinkRow from './DeskLinkRow.vue';
</script>

<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5">
    <header class="mb-4">
      <h2 class="text-base font-semibold text-gray-900">Mappings</h2>
      <p class="text-sm text-gray-500 mt-1">Mapping tables live inside Cashew Settings on the Desk.</p>
    </header>

    <div class="divide-y divide-gray-100">
      <DeskLinkRow
        label="Cashew Category Mapping"
        href="/app/cashew-settings#cashew_category_mapping"
        sublabel="Map Cashew categories to ERPNext income/expense accounts."
      />
      <DeskLinkRow
        label="Cashew Account Mapping"
        href="/app/cashew-settings#cashew_account_mapping"
        sublabel="Map Cashew accounts to ERPNext cash/bank/credit-card accounts."
      />
    </div>
  </section>
</template>
