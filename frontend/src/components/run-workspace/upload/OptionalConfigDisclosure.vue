<script setup>
import { ref } from 'vue';
import { Autocomplete, Input } from 'frappe-ui';
import { ChevronDown, ChevronRight } from 'lucide-vue-next';

const props = defineProps({
  balanceAdjustmentAccount: { type: [String, null], default: null },
  jeRoundingTolerance: { type: [Number, String], default: 0.01 },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['update:balanceAdjustmentAccount', 'update:jeRoundingTolerance']);

const open = ref(false);

function onAccount(opt) {
  emit('update:balanceAdjustmentAccount', opt?.value ?? opt?.name ?? null);
}
function onTolerance(v) {
  emit('update:jeRoundingTolerance', v);
}
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white">
    <button
      type="button"
      class="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
      @click="open = !open"
    >
      <component :is="open ? ChevronDown : ChevronRight" :size="14" />
      Advanced
    </button>
    <div v-if="open" class="px-3 pb-3 space-y-3 border-t border-gray-100 pt-3">
      <div>
        <label class="text-xs font-medium text-gray-700 block mb-1">Balance adjustment account</label>
        <Autocomplete
          :modelValue="balanceAdjustmentAccount"
          :options="[]"
          :disabled="disabled"
          placeholder="Optional"
          reference_doctype="Cashew Import Run"
          reference_fieldname="balance_adjustment_account"
          @update:modelValue="onAccount"
        />
      </div>
      <div>
        <label class="text-xs font-medium text-gray-700 block mb-1">JE rounding tolerance</label>
        <Input
          type="number"
          step="0.01"
          :modelValue="jeRoundingTolerance"
          :disabled="disabled"
          @update:modelValue="onTolerance"
        />
      </div>
    </div>
  </div>
</template>
