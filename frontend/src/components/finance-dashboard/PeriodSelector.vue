<script setup>
import { ref, computed } from 'vue';
import { Dropdown, Button, Dialog, Input } from 'frappe-ui';
import { ChevronDown, Calendar } from 'lucide-vue-next';
import { resolvePeriodRange, formatRange, PERIOD_PRESET_LABELS } from '@/utils/period';

const props = defineProps({
  preset: { type: String, default: 'this-month' },
  period: { type: Object, default: () => ({ start: null, end: null }) },
});
const emit = defineEmits(['update:preset', 'update:period']);

const customOpen = ref(false);
const customDraft = ref({ start: '', end: '' });

const PRESETS = [
  'this-month',
  'last-month',
  'last-30-days',
  'last-90-days',
  'this-fiscal-year',
  'custom',
];

const label = computed(() => {
  const base = PERIOD_PRESET_LABELS[props.preset] || 'Period';
  if (props.preset === 'custom') return formatRange(props.period.start, props.period.end) || 'Custom';
  return base;
});

const dropdownOptions = computed(() => PRESETS.map((p) => ({
  label: PERIOD_PRESET_LABELS[p],
  onClick: () => selectPreset(p),
})));

function selectPreset(preset) {
  if (preset === 'custom') {
    customDraft.value = { start: props.period?.start || '', end: props.period?.end || '' };
    customOpen.value = true;
    return;
  }
  const range = resolvePeriodRange(preset);
  emit('update:preset', preset);
  emit('update:period', range || { start: null, end: null });
}

function applyCustom() {
  if (!customDraft.value.start || !customDraft.value.end) return;
  emit('update:preset', 'custom');
  emit('update:period', { start: customDraft.value.start, end: customDraft.value.end });
  customOpen.value = false;
}
</script>

<template>
  <div>
    <Dropdown :options="dropdownOptions">
      <template #default>
        <Button variant="outline" data-period-selector class="!px-3 !py-1.5">
          <span class="inline-flex items-center gap-2">
            <Calendar :size="14" class="text-gray-500" />
            <span class="truncate max-w-[10rem] leading-none">{{ label }}</span>
            <ChevronDown :size="14" class="text-gray-500" />
          </span>
        </Button>
      </template>
    </Dropdown>

    <Dialog :modelValue="customOpen" @update:modelValue="(v) => customOpen = v">
      <template #body>
        <div class="p-5 space-y-4">
          <h2 class="text-base font-semibold">Custom date range</h2>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="text-xs text-gray-600 block mb-1">Start</label>
              <Input type="date" :modelValue="customDraft.start" @update:modelValue="(v) => customDraft.start = v" />
            </div>
            <div>
              <label class="text-xs text-gray-600 block mb-1">End</label>
              <Input type="date" :modelValue="customDraft.end" @update:modelValue="(v) => customDraft.end = v" />
            </div>
          </div>
          <div class="flex justify-end gap-2">
            <Button variant="ghost" @click="customOpen = false">Cancel</Button>
            <Button variant="solid" theme="gray" :disabled="!customDraft.start || !customDraft.end" @click="applyCustom">Apply</Button>
          </div>
        </div>
      </template>
    </Dialog>
  </div>
</template>
