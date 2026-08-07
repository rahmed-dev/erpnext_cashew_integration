<script setup>
// The dashboard's bucket-width control. One picker, one width, every chart.
//
// It sits beside the period selector because the two are one decision: a period
// answers "over what", a width answers "at what resolution", and picking a year
// while every chart silently stays on days — which is exactly what happened
// before this existed — makes the period control look broken.
//
// The button shows what was DRAWN, not what was asked. On Automatic that means
// naming the width the server picked, so the reader is never left guessing what
// a point on the chart stands for.
import { computed } from 'vue';
import { Dropdown, Button } from 'frappe-ui';
import { ChevronDown, BarChart3 } from 'lucide-vue-next';
import {
  GRANULARITY_OPTIONS, granularityLabel, granularityWasWidened,
} from '@/utils/granularity';

const props = defineProps({
  // What the surface is asking for — an option `value`, usually 'auto'.
  modelValue: { type: String, default: 'auto' },
  // `dashboard_summary.series`, so the button can report what actually happened.
  series: { type: [Object, null], default: null },
});
const emit = defineEmits(['update:modelValue']);

const label = computed(() => {
  if (!props.series) {
    const opt = GRANULARITY_OPTIONS.find((o) => o.value === props.modelValue);
    return opt?.label || 'Automatic';
  }
  return granularityLabel(props.series);
});

const widened = computed(() => granularityWasWidened(props.series));

const options = computed(() => GRANULARITY_OPTIONS.map((o) => ({
  label: o.label,
  onClick: () => emit('update:modelValue', o.value),
})));
</script>

<template>
  <Dropdown :options="options">
    <template #default>
      <Button variant="outline" data-granularity-selector class="!px-3 !py-1.5">
        <span class="inline-flex items-center gap-2">
          <BarChart3 :size="14" class="text-gray-500" />
          <span class="truncate max-w-[9rem] leading-none">{{ label }}</span>
          <!-- The request was too fine for this period and was widened. Silence
               here would leave the control naming one width and the chart
               drawing another. -->
          <span v-if="widened" class="text-[10px] text-amber-600 leading-none">widened</span>
          <ChevronDown :size="14" class="text-gray-500" />
        </span>
      </Button>
    </template>
  </Dropdown>
</template>
