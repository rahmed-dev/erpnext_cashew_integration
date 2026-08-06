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
    <ul v-else class="space-y-1.5">
      <li v-for="item in items" :key="item.account">
        <div class="flex items-center justify-between text-xs mb-0.5">
          <span class="truncate min-w-0">{{ item.account }}</span>
          <AmountDisplay :amount="item.amount" :currency="currency" class="text-gray-700 font-medium tabular-nums shrink-0 ml-2" />
        </div>
        <div class="h-1 rounded bg-gray-100 overflow-hidden">
          <div
            class="h-full"
            :style="`width: ${total > 0 ? Math.max(2, Math.round((item.amount / total) * 100)) : 0}%; background: ${barColor};`"
          />
        </div>

        <!-- The "(Other)" row stands for accounts the top-10 cut off. Collapsed
             by default so the list keeps its length, but reachable in place —
             the alternative is a figure the reader can only chase down in the
             Desk report. -->
        <details v-if="(item.members || []).length" class="mt-1">
          <summary class="text-[11px] text-gray-400 cursor-pointer select-none">
            {{ item.members.length }} accounts
          </summary>
          <ul class="mt-1 space-y-1 pl-3 border-l border-gray-200">
            <li
              v-for="m in item.members"
              :key="m.account"
              class="flex items-center justify-between text-[11px] text-gray-500"
            >
              <span class="truncate min-w-0">{{ m.account }}</span>
              <AmountDisplay :amount="m.amount" :currency="currency" class="tabular-nums shrink-0 ml-2" />
            </li>
          </ul>
        </details>
      </li>
    </ul>
  </div>
</template>
