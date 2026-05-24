<script setup>
import ResultBanner from '@/components/run-workspace/completed/ResultBanner.vue';
import CountsGrid from '@/components/run-workspace/completed/CountsGrid.vue';
import PostedBreakdown from '@/components/run-workspace/completed/PostedBreakdown.vue';
import DangerZone from '@/components/run-workspace/completed/DangerZone.vue';
import PreviewTable from '@/components/run-workspace/preview/PreviewTable.vue';

defineProps({
  doc: { type: Object, required: true },
  rows: { type: Array, default: () => [] },
  runName: { type: [String, null], default: null },
});
const emit = defineEmits(['reload']);
</script>

<template>
  <div class="space-y-4">
    <ResultBanner :doc="doc" />
    <CountsGrid :doc="doc" />
    <PostedBreakdown :doc="doc" :rows="rows" />

    <details class="rounded-lg border border-gray-200 bg-white">
      <summary class="cursor-pointer text-sm font-medium px-4 py-3 hover:bg-gray-50">Row results</summary>
      <div class="px-4 py-3 border-t border-gray-100">
        <PreviewTable :rows="rows" :currency="doc?.company_currency || 'PKR'" />
      </div>
    </details>

    <DangerZone :doc="doc" @reload="emit('reload')" />
  </div>
</template>
