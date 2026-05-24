<script setup>
import { Button } from 'frappe-ui';

defineProps({
  saving: { type: Boolean, default: false },
});
const emit = defineEmits(['save', 'discard']);
</script>

<template>
  <div class="fixed bottom-0 inset-x-0 md:left-60 z-30 bg-white/95 backdrop-blur border-t border-gray-200">
    <div class="max-w-3xl mx-auto px-4 md:px-6 py-3 flex items-center justify-between gap-3">
      <div class="text-sm text-gray-600">You have unsaved changes.</div>
      <div class="flex items-center gap-2">
        <Button variant="ghost" :disabled="saving" @click="emit('discard')">Discard</Button>
        <Button variant="solid" theme="gray" :loading="saving" :disabled="saving" @click="emit('save')">
          Save changes
        </Button>
      </div>
    </div>
  </div>
</template>
