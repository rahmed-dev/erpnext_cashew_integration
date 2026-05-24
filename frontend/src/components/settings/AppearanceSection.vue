<script setup>
import AccentColorPicker from './AccentColorPicker.vue';
import CustomHexInput from './CustomHexInput.vue';

defineProps({
  form: { type: Object, required: true },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['accent', 'custom-hex']);
</script>

<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5">
    <header class="mb-4">
      <h2 class="text-base font-semibold text-gray-900">Appearance</h2>
      <p class="text-sm text-gray-500 mt-1">Used across buttons, links, charts &amp; focus rings.</p>
    </header>

    <div class="space-y-4">
      <div>
        <label class="text-sm font-medium text-gray-700 block mb-2">Accent color</label>
        <AccentColorPicker
          :modelValue="form.accent_color"
          :disabled="disabled"
          @change="(p) => emit('accent', p)"
        />
      </div>

      <CustomHexInput
        v-if="form.accent_color === 'Custom'"
        :modelValue="form.accent_color_custom"
        :disabled="disabled"
        @change="(hex) => emit('custom-hex', hex)"
      />
    </div>
  </section>
</template>
