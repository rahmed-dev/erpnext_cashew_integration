<script setup>
import { Lock } from 'lucide-vue-next';
</script>

<template>
  <div class="rounded-lg border border-amber-200 bg-amber-50 text-amber-900 px-4 py-3 flex items-start gap-3">
    <Lock :size="16" class="mt-0.5 shrink-0" />
    <p class="text-sm">
      Read-only — ask a System Manager to change Cashew Settings.
    </p>
  </div>
</template>
