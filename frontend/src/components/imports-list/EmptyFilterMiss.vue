<script setup>
import EmptyState from '@/components/shared/EmptyState.vue';
const emit = defineEmits(['clear']);
</script>

<template>
  <EmptyState
    illustration="empty-results"
    title="No runs match your filters."
    body="Try widening the date range, clearing status filters, or removing the company filter."
    :primary="{ label: 'Clear filters', action: () => emit('clear') }"
  />
</template>
