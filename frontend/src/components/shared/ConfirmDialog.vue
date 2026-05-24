<script setup>
import { Dialog, Button } from 'frappe-ui';
import { AlertTriangle, Info, ShieldAlert } from 'lucide-vue-next';

const props = defineProps({
  open: { type: Boolean, required: true },
  kind: { type: String, default: 'warning' }, // info | warning | danger
  title: { type: String, required: true },
  body: { type: String, required: true },
  confirmLabel: { type: String, default: 'Confirm' },
  cancelLabel: { type: String, default: 'Cancel' },
  confirming: { type: Boolean, default: false },
});

const emit = defineEmits(['update:open', 'confirm', 'cancel']);

const KIND_META = {
  info:    { icon: Info,          accent: 'text-blue-600 bg-blue-50',   theme: 'gray' },
  warning: { icon: AlertTriangle, accent: 'text-amber-600 bg-amber-50', theme: 'gray' },
  danger:  { icon: ShieldAlert,   accent: 'text-red-600 bg-red-50',     theme: 'red' },
};
function meta() { return KIND_META[props.kind] || KIND_META.warning; }

function close() { emit('update:open', false); emit('cancel'); }
function confirm() { emit('confirm'); }
</script>

<template>
  <Dialog :modelValue="open" @update:modelValue="(v) => emit('update:open', v)">
    <template #body>
      <div class="p-5">
        <div class="flex items-start gap-3">
          <span :class="['h-10 w-10 rounded-full flex items-center justify-center shrink-0', meta().accent]">
            <component :is="meta().icon" :size="20" />
          </span>
          <div class="flex-1 min-w-0">
            <h2 class="text-base font-semibold text-gray-900">{{ title }}</h2>
            <p class="text-sm text-gray-600 mt-1">{{ body }}</p>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-5">
          <Button variant="ghost" @click="close">{{ cancelLabel }}</Button>
          <Button
            variant="solid"
            :theme="meta().theme"
            :loading="confirming"
            :disabled="confirming"
            @click="confirm"
          >
            {{ confirmLabel }}
          </Button>
        </div>
      </div>
    </template>
  </Dialog>
</template>
