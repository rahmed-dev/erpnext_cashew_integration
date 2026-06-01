<script setup>
import { ref, computed } from 'vue';
import { Input } from 'frappe-ui';
import { Link } from 'frappe-ui/frappe';
import { ChevronDown, ChevronRight } from 'lucide-vue-next';

const props = defineProps({
  balanceAdjustmentAccount: { type: [String, null], default: null },
  jeRoundingTolerance: { type: [Number, String], default: 0.01 },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['update:balanceAdjustmentAccount', 'update:jeRoundingTolerance']);

const open = ref(false);

const account = computed({
  get: () => props.balanceAdjustmentAccount || '',
  set: (v) => emit('update:balanceAdjustmentAccount', v || null),
});

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
        <Link
          v-model="account"
          doctype="Account"
          :filters="{ is_group: 0 }"
          :disabled="disabled"
          placeholder="Optional"
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
