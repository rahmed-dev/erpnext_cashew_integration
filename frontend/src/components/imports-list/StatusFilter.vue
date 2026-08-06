<script setup>
import { ref, computed } from 'vue';
import { Check, ChevronDown } from 'lucide-vue-next';

const props = defineProps({ modelValue: { type: Array, default: () => [] } });
const emit = defineEmits(['update:modelValue']);

const STATUSES = [
  'Draft','Parsed','Validated','Queued','Processing',
  'Completed','Failed','Cancelled','Reverting','Reverted','Revert-Failed',
];

const open = ref(false);

const label = computed(() => {
  if (!props.modelValue.length) return 'Status';
  if (props.modelValue.length === 1) return `Status: ${props.modelValue[0]}`;
  return `Status: ${props.modelValue.length} selected`;
});

function toggle(v) {
  const next = new Set(props.modelValue);
  if (next.has(v)) next.delete(v); else next.add(v);
  emit('update:modelValue', Array.from(next));
}
function selectAll() { emit('update:modelValue', [...STATUSES]); }
function clearAll() { emit('update:modelValue', []); }
</script>

<template>
  <div class="relative">
    <button
      type="button"
      class="h-8 px-3 inline-flex items-center gap-1.5 rounded-full border border-gray-300 text-xs font-medium hover:bg-gray-50"
      :class="modelValue.length ? 'border-cs-accent text-cs-accent-700 bg-cs-accent-50' : 'text-gray-700'"
      :aria-expanded="open"
      @click="open = !open"
    >
      {{ label }}
      <ChevronDown :size="12" />
    </button>
    <div
      v-if="open"
      class="absolute z-50 mt-1 min-w-[200px] bg-white border border-gray-200 rounded-lg shadow-md p-1"
      @click.stop
    >
      <div class="flex items-center justify-between px-2 py-1">
        <button class="text-[11px] text-cs-accent-700 hover:underline" @click="selectAll">Select all</button>
        <button class="text-[11px] text-gray-500 hover:underline" @click="clearAll">Clear</button>
      </div>
      <div class="max-h-64 overflow-y-auto py-1">
        <button
          v-for="s in STATUSES"
          :key="s"
          type="button"
          class="w-full flex items-center justify-between px-2 py-1.5 rounded text-xs hover:bg-gray-50"
          @click="toggle(s)"
        >
          <span>{{ s }}</span>
          <Check v-if="modelValue.includes(s)" :size="14" class="text-cs-accent" />
        </button>
      </div>
    </div>
    <!-- Menu is an overlay, so it owns z-50 per the design-philosophy scale — at z-30
         it tied with MobileBottomNav/SelectionFooter and DOM order could paint it
         underneath them on a phone. Backdrop sits at z-40: above app chrome so an
         outside tap closes the menu, below the panel itself. -->
    <button v-if="open" class="fixed inset-0 z-40 cursor-default" aria-hidden="true" @click="open = false" />
  </div>
</template>
