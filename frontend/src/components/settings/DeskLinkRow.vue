<script setup>
import { ExternalLink } from 'lucide-vue-next';

defineProps({
  label: { type: String, required: true },
  sublabel: { type: String, default: '' },
  href: { type: String, required: true },
});
</script>

<template>
  <a
    :href="href"
    class="flex items-center justify-between py-3 group"
  >
    <div class="min-w-0">
      <div class="text-sm font-medium text-gray-900 group-hover:text-[var(--cs-accent)]">{{ label }}</div>
      <div v-if="sublabel" class="text-xs text-gray-500 mt-0.5">{{ sublabel }}</div>
    </div>
    <span class="text-sm text-[var(--cs-accent)] inline-flex items-center gap-1 shrink-0">
      Manage on Desk
      <ExternalLink :size="14" />
    </span>
  </a>
</template>
