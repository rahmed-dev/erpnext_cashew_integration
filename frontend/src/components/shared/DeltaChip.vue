<script setup>
import { computed } from 'vue';
import { ArrowUp, ArrowDown, Minus } from 'lucide-vue-next';

const props = defineProps({
  current: { type: [Number, null], default: null },
  prior: { type: [Number, null], default: null },
  invert: { type: Boolean, default: false }, // expense delta is "good" when negative
});

const delta = computed(() => {
  if (props.prior == null || props.current == null) return null;
  const d = props.current - props.prior;
  if (Math.abs(d) < 0.01) return 0;
  return d;
});

const pct = computed(() => {
  if (delta.value == null || !props.prior) return null;
  return Math.round((delta.value / Math.abs(props.prior)) * 100);
});

const tone = computed(() => {
  if (delta.value == null) return 'neutral';
  if (delta.value === 0) return 'neutral';
  const positive = props.invert ? delta.value < 0 : delta.value > 0;
  return positive ? 'pos' : 'neg';
});

const Icon = computed(() => {
  if (delta.value == null || delta.value === 0) return Minus;
  return delta.value > 0 ? ArrowUp : ArrowDown;
});
</script>

<template>
  <span
    v-if="delta != null"
    :class="[
      'inline-flex items-center gap-0.5 text-[10px] font-medium px-1 py-0 rounded',
      tone === 'pos' && 'text-green-700 bg-green-50',
      tone === 'neg' && 'text-red-700 bg-red-50',
      tone === 'neutral' && 'text-gray-500 bg-gray-50',
    ]"
  >
    <component :is="Icon" :size="9" />
    <span v-if="pct != null">{{ Math.abs(pct) }}%</span>
  </span>
</template>
