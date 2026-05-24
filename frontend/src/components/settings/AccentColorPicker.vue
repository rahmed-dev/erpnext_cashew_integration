<script setup>
import { Check } from 'lucide-vue-next';

const PRESETS = [
  { id: 'Indigo',       hex: '#4f46e5' },
  { id: 'Teal',         hex: '#0d9488' },
  { id: 'Burnt Orange', hex: '#ea580c' },
  { id: 'Monochrome',   hex: '#1f2937' },
  { id: 'Cyan',         hex: '#0891b2' },
  { id: 'Custom',       hex: null },
];

defineProps({
  modelValue: { type: String, default: 'Indigo' },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['change']);

function pick(p) {
  emit('change', p.id);
}
</script>

<template>
  <div role="radiogroup" aria-label="Accent color" class="flex flex-wrap gap-3">
    <button
      v-for="p in PRESETS"
      :key="p.id"
      type="button"
      role="radio"
      :aria-checked="modelValue === p.id"
      :disabled="disabled"
      class="focus:outline-none"
      :title="p.id"
      :aria-label="p.id"
      @click="pick(p)"
    >
      <span
        :class="[
          'w-9 h-9 rounded-md relative flex items-center justify-center',
          modelValue === p.id ? 'ring-2 ring-offset-2 ring-[var(--cs-accent)]' : 'ring-1 ring-gray-200 hover:ring-2 hover:ring-gray-300',
          disabled && 'opacity-50 cursor-not-allowed',
        ]"
        :style="p.hex
          ? `background-color: ${p.hex};`
          : 'background: conic-gradient(red, orange, yellow, green, blue, purple, red);'"
      >
        <Check v-if="modelValue === p.id" :size="14" class="text-white drop-shadow" />
      </span>
    </button>
  </div>
</template>
