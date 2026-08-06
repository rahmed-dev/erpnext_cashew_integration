<script setup>
import { computed } from 'vue';

const props = defineProps({
  doc: { type: Object, required: true },
});

const tiles = computed(() => {
  const t = [
    { label: 'Total',    value: props.doc?.rows_total ?? 0 },
    { label: 'Valid',    value: props.doc?.rows_valid ?? 0, tone: 'green' },
    { label: 'Posted',   value: props.doc?.rows_posted ?? 0, tone: 'green' },
    { label: 'Failed',   value: props.doc?.rows_failed ?? 0, tone: 'red' },
    { label: 'Skipped',  value: props.doc?.rows_skipped ?? 0, tone: 'amber' },
  ];
  // Only when it happened. A permanent zero tile would train people to ignore the
  // one number that says this import rewrote already-submitted GL.
  if (props.doc?.rows_resynced) {
    t.push({ label: 'Resynced', value: props.doc.rows_resynced, tone: 'sky' });
  }
  return t;
});
</script>

<template>
  <div :class="['grid grid-cols-2 gap-3', tiles.length > 5 ? 'md:grid-cols-6' : 'md:grid-cols-5']">
    <div
      v-for="t in tiles"
      :key="t.label"
      class="rounded-lg border border-gray-200 bg-white px-3 py-2"
    >
      <div class="text-[10px] uppercase tracking-wide text-gray-500">{{ t.label }}</div>
      <div :class="[
        'text-xl font-semibold tabular-nums mt-0.5',
        t.tone === 'green' && 'text-green-700',
        t.tone === 'red' && 'text-red-700',
        t.tone === 'amber' && 'text-amber-700',
        t.tone === 'sky' && 'text-sky-700',
      ]">{{ t.value }}</div>
    </div>
  </div>
</template>
