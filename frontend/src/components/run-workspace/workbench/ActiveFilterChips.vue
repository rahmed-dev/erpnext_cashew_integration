<script setup>
import { computed } from 'vue';
import { X } from 'lucide-vue-next';
import { FILTER_FACETS } from './registries/filters';

const props = defineProps({
  filters: { type: Object, default: () => ({}) },
  search: { type: String, default: '' },
});
const emit = defineEmits(['remove', 'clear-all', 'clear-search']);

const chips = computed(() => {
  const out = [];
  for (const facet of FILTER_FACETS) {
    const value = props.filters[facet.id];
    if (value == null) continue;
    if (Array.isArray(value) && value.length === 0) continue;
    out.push({ id: facet.id, label: facet.chipLabel(value) });
  }
  return out;
});
</script>

<template>
  <div v-if="chips.length || search" class="flex flex-wrap items-center gap-2">
    <span
      v-if="search"
      class="inline-flex items-center gap-1 text-xs bg-[var(--cs-accent-50)] text-[var(--cs-accent)] px-2 py-0.5 rounded-full"
    >
      Search: "{{ search }}"
      <button class="hover:bg-white/40 rounded-full p-0.5" @click="emit('clear-search')"><X :size="10" /></button>
    </span>
    <span
      v-for="chip in chips"
      :key="chip.id"
      class="inline-flex items-center gap-1 text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded-full"
    >
      {{ chip.label }}
      <button class="hover:bg-gray-200 rounded-full p-0.5" @click="emit('remove', chip.id)"><X :size="10" /></button>
    </span>
    <button
      v-if="chips.length"
      class="text-xs text-gray-500 hover:text-gray-800 underline ml-1"
      @click="emit('clear-all')"
    >
      Clear all
    </button>
  </div>
</template>
