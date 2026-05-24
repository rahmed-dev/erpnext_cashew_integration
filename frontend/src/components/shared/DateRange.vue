<script setup>
import { computed } from 'vue';
import { formatRange } from '@/utils/period';

const props = defineProps({
  start: { type: String, default: null },
  end:   { type: String, default: null },
  format: { type: String, default: 'short' }, // 'short' | 'long'
  nullText: { type: String, default: '—' },
});

const text = computed(() => formatRange(props.start, props.end, props.format) || props.nullText);
</script>

<template>
  <span class="text-sm text-gray-700 tabular-nums">{{ text }}</span>
</template>
