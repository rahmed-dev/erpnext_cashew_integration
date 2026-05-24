<script setup>
import { computed, ref } from 'vue';
import StatusPill from '@/components/shared/StatusPill.vue';
import AmountDisplay from '@/components/shared/AmountDisplay.vue';

const props = defineProps({
  rows: { type: Array, default: () => [] },
  currency: { type: String, default: 'PKR' },
});

const PAGE_SIZE = 25;
const page = ref(0);

const totalPages = computed(() => Math.max(1, Math.ceil(props.rows.length / PAGE_SIZE)));
const pageRows = computed(() => props.rows.slice(page.value * PAGE_SIZE, (page.value + 1) * PAGE_SIZE));

function prev() { if (page.value > 0) page.value -= 1; }
function next() { if (page.value < totalPages.value - 1) page.value += 1; }
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white overflow-x-auto">
    <table class="min-w-full text-sm">
      <thead class="bg-gray-50 text-xs text-gray-500 uppercase">
        <tr>
          <th class="px-3 py-2 text-left">#</th>
          <th class="px-3 py-2 text-left">Date</th>
          <th class="px-3 py-2 text-left">Account</th>
          <th class="px-3 py-2 text-right">Amount</th>
          <th class="px-3 py-2 text-left">Type</th>
          <th class="px-3 py-2 text-left">Category</th>
          <th class="px-3 py-2 text-left">Note</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in pageRows" :key="r.row_idx" class="border-t border-gray-100">
          <td class="px-3 py-1.5 text-gray-500 tabular-nums">{{ r.row_idx }}</td>
          <td class="px-3 py-1.5">{{ r.txn_date || '—' }}</td>
          <td class="px-3 py-1.5 truncate max-w-[14ch]" :title="r.raw_account">{{ r.raw_account || '—' }}</td>
          <td class="px-3 py-1.5 text-right">
            <AmountDisplay :amount="r.base_amount" :currency="currency" :signed="true" />
          </td>
          <td class="px-3 py-1.5">
            <StatusPill v-if="r.txn_type" kind="txn-type" :value="r.txn_type" />
            <span v-else class="text-gray-400">—</span>
          </td>
          <td class="px-3 py-1.5">
            <div class="text-sm">{{ r.category || '—' }}</div>
            <div v-if="r.sub_category" class="text-xs text-gray-500">{{ r.sub_category }}</div>
          </td>
          <td class="px-3 py-1.5 truncate max-w-[24ch]" :title="r.note">{{ r.note || '' }}</td>
        </tr>
      </tbody>
    </table>
    <div class="flex items-center justify-between px-3 py-2 border-t border-gray-100 text-xs text-gray-500">
      <span>Page {{ page + 1 }} of {{ totalPages }} · {{ rows.length }} rows</span>
      <div class="flex gap-1">
        <button class="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-40" :disabled="page === 0" @click="prev">Previous</button>
        <button class="px-2 py-1 rounded hover:bg-gray-100 disabled:opacity-40" :disabled="page >= totalPages - 1" @click="next">Next</button>
      </div>
    </div>
  </div>
</template>
