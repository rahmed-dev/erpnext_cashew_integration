<script setup>
import RowCard from './RowCard.vue';

defineProps({
  rows: { type: Array, default: () => [] },
  selected: { type: Set, default: () => new Set() },
  editable: { type: Boolean, default: true },
  recentPatches: { type: Set, default: () => new Set() },
});
const emit = defineEmits(['select-toggle', 'row-action', 'row-click']);
</script>

<template>
  <div v-if="rows.length === 0" class="rounded-lg border border-gray-200 bg-white px-3 py-8 text-center text-sm text-gray-500">
    No rows match the current filters.
  </div>
  <div v-else class="space-y-2">
    <RowCard
      v-for="row in rows"
      :key="row.row_idx"
      :row="row"
      :selected="selected.has(row.row_idx)"
      :editable="editable"
      :pulse="recentPatches.has(row.row_idx)"
      @select-toggle="(idx) => emit('select-toggle', idx)"
      @row-action="(p) => emit('row-action', p)"
      @row-click="(r) => emit('row-click', r)"
    />
  </div>
</template>
