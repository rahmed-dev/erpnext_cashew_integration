<script setup>
import { computed, ref, watch } from 'vue';
import { Input } from 'frappe-ui';

const props = defineProps({
  modelValue: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['change']);

const local = ref(props.modelValue || '');
watch(() => props.modelValue, (v) => { local.value = v || ''; });

const HEX_RE = /^#[0-9a-fA-F]{6}$/;
const isValid = computed(() => HEX_RE.test(local.value));
const showError = computed(() => local.value.length > 0 && !isValid.value);

function onInput(value) {
  let v = String(value || '');
  if (v && !v.startsWith('#')) v = '#' + v.replace(/[^0-9a-fA-F]/g, '');
  if (v.length > 7) v = v.slice(0, 7);
  local.value = v;
  emit('change', v);
}
</script>

<template>
  <div class="space-y-1">
    <label class="text-sm font-medium text-gray-700 block">Custom hex color</label>
    <div class="flex items-center gap-3">
      <span
        class="w-9 h-9 rounded-md ring-1 ring-gray-200 shrink-0"
        :style="isValid ? `background-color: ${local};` : 'background: repeating-linear-gradient(45deg, #f3f4f6, #f3f4f6 4px, #e5e7eb 4px, #e5e7eb 8px);'"
      />
      <Input
        type="text"
        :modelValue="local"
        placeholder="#4f46e5"
        :disabled="disabled"
        class="font-mono w-36"
        maxlength="7"
        @update:modelValue="onInput"
      />
    </div>
    <p v-if="showError" class="text-xs text-red-600">Enter a 6-digit hex color like <code>#4f46e5</code>.</p>
    <p v-else class="text-xs text-gray-500">6-digit hex color. We'll derive lighter/darker shades automatically.</p>
  </div>
</template>
