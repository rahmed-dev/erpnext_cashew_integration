<script setup>
import { computed } from 'vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';

const props = defineProps({
  title: { type: String, required: true },
  items: { type: Array, default: () => [] },
  currency: { type: String, default: 'PKR' },
  tone: { type: String, default: 'pos' }, // pos | neg
});

const total = computed(() => props.items.reduce((s, i) => s + (i.amount || 0), 0));
const barColor = computed(() => props.tone === 'pos' ? 'var(--cs-accent)' : '#334155');
</script>

<template>
  <div>
    <div class="text-xs font-medium text-gray-700 mb-2">{{ title }}</div>
    <div v-if="items.length === 0" class="text-xs text-gray-400 italic">No data this period.</div>
    <ul v-else class="space-y-2">
      <li v-for="item in items" :key="item.account">
        <div class="flex items-center justify-between text-xs mb-0.5">
          <span class="truncate min-w-0">{{ item.account }}</span>
          <AmountDisplay :amount="item.amount" :currency="currency" class="text-gray-700 font-medium tabular-nums shrink-0 ml-2" />
        </div>
        <div class="h-1.5 rounded bg-gray-100 overflow-hidden">
          <div
            class="h-full"
            :style="`width: ${total > 0 ? Math.max(2, Math.round((item.amount / total) * 100)) : 0}%; background: ${barColor};`"
          />
        </div>
      </li>
    </ul>
  </div>
</template>
