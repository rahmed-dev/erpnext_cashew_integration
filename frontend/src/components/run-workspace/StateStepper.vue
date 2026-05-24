<script setup>
import { computed } from 'vue';
import { Check } from 'lucide-vue-next';
import { useIsMobile } from '@/state/useIsMobile';

const STEPS = [
  { id: 'upload',    label: 'Upload',    statuses: ['Draft'] },
  { id: 'preview',   label: 'Preview',   statuses: ['Parsed'] },
  { id: 'workbench', label: 'Workbench', statuses: ['Validated', 'Queued', 'Processing'] },
  { id: 'done',      label: 'Done',      statuses: ['Completed', 'Failed', 'Cancelled', 'Reverting', 'Reverted', 'Revert-Failed'] },
];

const props = defineProps({ status: { type: [String, null], default: null } });
const isMobile = useIsMobile();

const activeIndex = computed(() => STEPS.findIndex((s) => s.statuses.includes(props.status)));
const activeStep = computed(() => STEPS[activeIndex.value] || STEPS[0]);
</script>

<template>
  <div class="border-b border-gray-200 bg-white px-4 py-2">
    <div v-if="isMobile" class="text-xs text-gray-600">
      Step {{ Math.max(activeIndex + 1, 1) }} of 4: <span class="font-medium text-gray-900">{{ activeStep.label }}</span>
    </div>
    <ol v-else class="flex items-center gap-2 max-w-3xl">
      <li
        v-for="(step, i) in STEPS"
        :key="step.id"
        class="flex items-center gap-2 flex-1"
      >
        <span
          :class="[
            'inline-flex items-center justify-center h-5 w-5 rounded-full text-[10px] font-semibold',
            i < activeIndex && 'bg-green-100 text-green-700',
            i === activeIndex && 'bg-[var(--cs-accent)] text-white',
            i > activeIndex && 'bg-gray-100 text-gray-500',
          ]"
        >
          <Check v-if="i < activeIndex" :size="11" />
          <template v-else>{{ i + 1 }}</template>
        </span>
        <span
          :class="[
            'text-xs',
            i === activeIndex ? 'text-gray-900 font-medium' : 'text-gray-500',
          ]"
        >
          {{ step.label }}
        </span>
        <span v-if="i < STEPS.length - 1" class="h-px flex-1 bg-gray-200 mx-1" />
      </li>
    </ol>
  </div>
</template>
