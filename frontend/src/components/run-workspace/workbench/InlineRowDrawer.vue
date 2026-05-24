<script setup>
import { ref, computed } from 'vue';
import { X } from 'lucide-vue-next';

const props = defineProps({
  row: { type: [Object, null], default: null },
});
const emit = defineEmits(['close']);

const showJson = ref(false);

const visibleFields = computed(() => {
  if (!props.row) return [];
  return Object.entries(props.row)
    .filter(([k]) => !k.startsWith('_') && typeof props.row[k] !== 'function')
    .map(([k, v]) => ({ k, v }));
});
</script>

<template>
  <Transition name="drawer">
    <div v-if="row" class="fixed inset-0 z-40">
      <div class="absolute inset-0 bg-black/30" @click="emit('close')" />
      <aside class="absolute right-0 top-0 bottom-0 w-full sm:w-[480px] bg-white shadow-xl flex flex-col">
        <header class="px-4 py-3 border-b border-gray-200 flex items-center gap-2">
          <h2 class="text-base font-semibold text-gray-900">Row #{{ row.row_idx }}</h2>
          <span class="flex-1" />
          <button class="h-8 w-8 rounded hover:bg-gray-100 flex items-center justify-center text-gray-500" aria-label="Close" @click="emit('close')"><X :size="16" /></button>
        </header>
        <div class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
          <div class="flex items-center gap-2 text-xs">
            <button :class="['px-2 py-1 rounded', !showJson ? 'bg-gray-100 font-medium' : 'hover:bg-gray-50']" @click="showJson = false">Fields</button>
            <button :class="['px-2 py-1 rounded', showJson ? 'bg-gray-100 font-medium' : 'hover:bg-gray-50']" @click="showJson = true">JSON</button>
          </div>

          <pre v-if="showJson" class="text-xs bg-gray-50 border border-gray-200 rounded p-2 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(row, null, 2) }}</pre>

          <dl v-else class="grid grid-cols-[160px_1fr] gap-y-1.5 text-sm">
            <template v-for="f in visibleFields" :key="f.k">
              <dt class="text-gray-500">{{ f.k }}</dt>
              <dd class="text-gray-900 truncate" :title="String(f.v ?? '')">{{ f.v ?? '—' }}</dd>
            </template>
          </dl>
        </div>
      </aside>
    </div>
  </Transition>
</template>

<style scoped>
.drawer-enter-from, .drawer-leave-to { opacity: 0; }
.drawer-enter-active, .drawer-leave-active { transition: opacity 150ms ease-out; }
.drawer-enter-active aside, .drawer-leave-active aside { transition: transform 200ms ease-out; }
.drawer-enter-from aside, .drawer-leave-to aside { transform: translateX(100%); }
</style>
