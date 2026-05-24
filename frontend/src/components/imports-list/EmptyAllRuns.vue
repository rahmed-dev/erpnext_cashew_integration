<script setup>
import EmptyState from '@/components/shared/EmptyState.vue';
</script>

<template>
  <EmptyState
    illustration="first-run"
    title="No imports yet."
    body="Start your first cashew import — upload a bank or accounting CSV and we'll guide you through preview, validate, and post."
    :primary="{ label: '+ New Import', action: '/runs/new' }"
  />
</template>
