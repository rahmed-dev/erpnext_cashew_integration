<script setup>
import { computed } from 'vue';
import { ChevronLeft, ChevronRight } from 'lucide-vue-next';

const props = defineProps({
  start: { type: Number, required: true },
  length: { type: Number, required: true },
  total: { type: Number, required: true },
});
const emit = defineEmits(['page']);

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.length)));
const currentPage = computed(() => Math.floor(props.start / props.length) + 1);

function buttons() {
  const total = pageCount.value;
  const cur = currentPage.value;
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  if (cur <= 4) return [1, 2, 3, 4, 5, '…', total];
  if (cur >= total - 3) return [1, '…', total - 4, total - 3, total - 2, total - 1, total];
  return [1, '…', cur - 1, cur, cur + 1, '…', total];
}

function go(p) {
  if (typeof p !== 'number') return;
  const next = (p - 1) * props.length;
  if (next === props.start) return;
  emit('page', { start: next, length: props.length });
}
</script>

<template>
  <nav v-if="total > length" class="flex items-center justify-between mt-4 text-xs" aria-label="Pagination">
    <p class="text-gray-500">
      Showing {{ start + 1 }}–{{ Math.min(start + length, total) }} of {{ total }}
    </p>
    <div class="flex items-center gap-1">
      <button
        class="h-7 w-7 inline-flex items-center justify-center rounded-md border border-gray-200 hover:bg-gray-50 disabled:opacity-40"
        :disabled="currentPage === 1"
        aria-label="Previous page"
        @click="go(currentPage - 1)"
      ><ChevronLeft :size="14" /></button>
      <template v-for="(p, idx) in buttons()" :key="`${p}-${idx}`">
        <button
          v-if="typeof p === 'number'"
          class="h-7 min-w-[1.75rem] px-2 rounded-md border text-xs"
          :class="p === currentPage ? 'border-cs-accent bg-cs-accent text-white font-semibold' : 'border-gray-200 hover:bg-gray-50 text-gray-700'"
          @click="go(p)"
        >{{ p }}</button>
        <span v-else class="px-1 text-gray-400">…</span>
      </template>
      <button
        class="h-7 w-7 inline-flex items-center justify-center rounded-md border border-gray-200 hover:bg-gray-50 disabled:opacity-40"
        :disabled="currentPage === pageCount"
        aria-label="Next page"
        @click="go(currentPage + 1)"
      ><ChevronRight :size="14" /></button>
    </div>
  </nav>
</template>
