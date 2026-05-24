<script setup>
import { ref } from 'vue';
import { ChevronDown } from 'lucide-vue-next';
import { Dialog, Input, Button } from 'frappe-ui';

const props = defineProps({
  modelValue: { type: String, default: 'any' },
  range: { type: Object, default: null },
});
const emit = defineEmits(['update:modelValue', 'update:range']);

const OPTIONS = [
  { value: 'any',           label: 'Any time' },
  { value: 'this-month',    label: 'This month' },
  { value: 'last-month',    label: 'Last month' },
  { value: 'last-3-months', label: 'Last 3 months' },
  { value: 'custom',        label: 'Custom…' },
];

const open = ref(false);
const customOpen = ref(false);
const customStart = ref(props.range?.start || '');
const customEnd = ref(props.range?.end || '');

function pick(opt) {
  if (opt.value === 'custom') {
    customStart.value = props.range?.start || '';
    customEnd.value = props.range?.end || '';
    customOpen.value = true;
    open.value = false;
    return;
  }
  emit('update:modelValue', opt.value);
  emit('update:range', null);
  open.value = false;
}
function saveCustom() {
  if (!customStart.value || !customEnd.value) return;
  emit('update:modelValue', 'custom');
  emit('update:range', { start: customStart.value, end: customEnd.value });
  customOpen.value = false;
}

function currentLabel() {
  return OPTIONS.find((o) => o.value === props.modelValue)?.label || 'Any time';
}
</script>

<template>
  <div class="relative">
    <button
      type="button"
      class="h-8 px-3 inline-flex items-center gap-1.5 rounded-full border border-gray-300 text-xs font-medium hover:bg-gray-50"
      :class="modelValue !== 'any' ? 'border-cs-accent text-cs-accent-700 bg-cs-accent-50' : 'text-gray-700'"
      :aria-expanded="open"
      @click="open = !open"
    >
      Period: {{ currentLabel() }}
      <ChevronDown :size="12" />
    </button>
    <div
      v-if="open"
      class="absolute z-30 mt-1 min-w-[170px] bg-white border border-gray-200 rounded-md shadow-md py-1"
      @click.stop
    >
      <button
        v-for="opt in OPTIONS"
        :key="opt.value"
        type="button"
        class="block w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50"
        :class="modelValue === opt.value ? 'text-cs-accent-700 font-medium' : 'text-gray-700'"
        @click="pick(opt)"
      >{{ opt.label }}</button>
    </div>
    <button v-if="open" class="fixed inset-0 z-20 cursor-default" aria-hidden="true" @click="open = false" />

    <Dialog v-model="customOpen">
      <template #body>
        <div class="p-5">
          <h3 class="text-base font-semibold mb-3">Custom period</h3>
          <div class="grid grid-cols-2 gap-3">
            <label class="block text-xs text-gray-600">
              Start
              <Input v-model="customStart" type="date" class="mt-1" />
            </label>
            <label class="block text-xs text-gray-600">
              End
              <Input v-model="customEnd" type="date" class="mt-1" />
            </label>
          </div>
          <div class="flex justify-end gap-2 mt-4">
            <Button variant="ghost" @click="customOpen = false">Cancel</Button>
            <Button variant="solid" theme="accent" :disabled="!customStart || !customEnd" @click="saveCustom">
              Apply
            </Button>
          </div>
        </div>
      </template>
    </Dialog>
  </div>
</template>
