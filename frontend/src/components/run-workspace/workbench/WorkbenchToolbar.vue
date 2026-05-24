<script setup>
import { computed, ref } from 'vue';
import { Button, Dropdown, Input } from 'frappe-ui';
import { Search, Filter, Columns, ChevronDown } from 'lucide-vue-next';
import { FILTER_FACETS } from './registries/filters';
import { COLUMN_PRESETS, COLUMN_DEFS } from './registries/columns';

const props = defineProps({
  search: { type: String, default: '' },
  filters: { type: Object, default: () => ({}) },
  preset: { type: String, default: 'Compact' },
  visibleColumns: { type: Array, default: () => [] },
  rows: { type: Array, default: () => [] },
  editable: { type: Boolean, default: true },
});
const emit = defineEmits(['update:search', 'update:filters', 'update:preset', 'update:visibleColumns', 'validate']);

const filtersOpen = ref(false);

const presetOptions = computed(() => Object.keys(COLUMN_PRESETS).map((id) => ({
  label: id,
  onClick: () => emit('update:preset', id),
})));

const colToggleOptions = computed(() => COLUMN_DEFS
  .filter((c) => c.header)
  .map((c) => ({
    label: `${props.visibleColumns.includes(c.id) ? '✓ ' : '   '}${c.header}`,
    onClick: () => {
      const set = new Set(props.visibleColumns);
      if (set.has(c.id)) set.delete(c.id); else set.add(c.id);
      emit('update:visibleColumns', Array.from(set));
    },
  })));

function setFacet(facetId, value) {
  const next = { ...props.filters };
  if (value == null || (Array.isArray(value) && value.length === 0)) {
    delete next[facetId];
  } else {
    next[facetId] = value;
  }
  emit('update:filters', next);
}

function isSelected(facetId, option) {
  const v = props.filters[facetId];
  if (Array.isArray(v)) return v.includes(option);
  return v === option;
}

function toggleSelectOption(facet, option) {
  const v = props.filters[facet.id];
  const current = Array.isArray(v) ? [...v] : [];
  const i = current.indexOf(option);
  if (i === -1) current.push(option); else current.splice(i, 1);
  setFacet(facet.id, current);
}

function setTriState(facet, option) {
  const v = props.filters[facet.id];
  setFacet(facet.id, v === option ? null : option);
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-2">
    <div class="relative w-full md:w-72">
      <Search :size="14" class="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" />
      <Input
        type="text"
        :modelValue="search"
        placeholder="Search rows"
        class="pl-7"
        @update:modelValue="(v) => emit('update:search', v)"
      />
    </div>

    <Dropdown :options="presetOptions">
      <template #default>
        <Button variant="outline">
          <Columns :size="14" class="mr-1" />
          {{ preset }}
          <ChevronDown :size="14" class="ml-1" />
        </Button>
      </template>
    </Dropdown>

    <Dropdown :options="colToggleOptions">
      <template #default>
        <Button variant="outline">Columns ({{ visibleColumns.length }})</Button>
      </template>
    </Dropdown>

    <Button variant="outline" @click="filtersOpen = !filtersOpen">
      <Filter :size="14" class="mr-1" />
      Filters
    </Button>

    <span class="flex-1" />

    <Button v-if="editable" variant="solid" theme="gray" @click="emit('validate')">Re-validate run</Button>
  </div>

  <div v-if="filtersOpen" class="mt-3 rounded-lg border border-gray-200 bg-white p-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
    <div v-for="facet in FILTER_FACETS" :key="facet.id">
      <div class="text-xs font-medium text-gray-700 mb-1">{{ facet.label }}</div>
      <div v-if="facet.type === 'select'" class="flex flex-wrap gap-1.5">
        <button
          v-for="opt in facet.options"
          :key="opt"
          type="button"
          :class="[
            'text-xs px-2 py-0.5 rounded-full border',
            isSelected(facet.id, opt) ? 'bg-[var(--cs-accent)] text-white border-transparent' : 'bg-white border-gray-300 text-gray-700 hover:border-gray-400',
          ]"
          @click="toggleSelectOption(facet, opt)"
        >
          {{ opt }}
        </button>
      </div>
      <div v-else-if="facet.type === 'tri-state'" class="flex gap-1.5">
        <button
          v-for="opt in facet.options"
          :key="opt"
          type="button"
          :class="[
            'text-xs px-2 py-0.5 rounded-full border',
            isSelected(facet.id, opt) ? 'bg-[var(--cs-accent)] text-white border-transparent' : 'bg-white border-gray-300 text-gray-700 hover:border-gray-400',
          ]"
          @click="setTriState(facet, opt)"
        >
          {{ opt }}
        </button>
      </div>
      <div v-else-if="facet.type === 'string-facet'" class="flex flex-wrap gap-1.5 max-h-32 overflow-y-auto">
        <button
          v-for="opt in Array.from(new Set(rows.map((r) => r[facet.id]).filter(Boolean))).sort().slice(0, 24)"
          :key="opt"
          type="button"
          :class="[
            'text-xs px-2 py-0.5 rounded-full border',
            isSelected(facet.id, opt) ? 'bg-[var(--cs-accent)] text-white border-transparent' : 'bg-white border-gray-300 text-gray-700 hover:border-gray-400',
          ]"
          @click="toggleSelectOption(facet, opt)"
        >
          {{ opt }}
        </button>
      </div>
    </div>
  </div>
</template>
