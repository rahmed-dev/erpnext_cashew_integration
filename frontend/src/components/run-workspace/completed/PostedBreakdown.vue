<script setup>
import { computed } from 'vue';

const props = defineProps({
  doc: { type: Object, required: true },
  rows: { type: Array, default: () => [] },
});

const breakdown = computed(() => {
  const byType = {};
  for (const r of props.rows) {
    if (!r.posted_doctype) continue;
    byType[r.posted_doctype] = (byType[r.posted_doctype] || 0) + 1;
  }
  return Object.entries(byType).sort((a, b) => b[1] - a[1]);
});
</script>

<template>
  <div v-if="breakdown.length" class="rounded-lg border border-gray-200 bg-white p-4">
    <h3 class="text-sm font-semibold text-gray-900 mb-2">Posted documents</h3>
    <ul class="text-sm space-y-1">
      <li v-for="[doctype, count] in breakdown" :key="doctype" class="flex items-center justify-between">
        <span class="text-gray-700">{{ doctype }}</span>
        <span class="tabular-nums text-gray-900 font-medium">{{ count }}</span>
      </li>
    </ul>
  </div>
</template>
