<script setup>
import { Plus } from 'lucide-vue-next';
import { Button } from 'frappe-ui';
import ImportCard from './ImportCard.vue';

defineProps({
  runs: { type: Array, default: () => [] },
});
const emit = defineEmits(['open', 'new-import']);
</script>

<template>
  <div class="rounded-lg border border-gray-200 bg-white p-4">
    <header class="flex items-center justify-between mb-3">
      <div>
        <h3 class="text-sm font-semibold text-gray-900">Recent imports</h3>
        <p class="text-xs text-gray-500">5 most recent runs</p>
      </div>
      <Button variant="ghost" theme="gray" :icon-left="Plus" @click="emit('new-import')">
        New Import
      </Button>
    </header>

    <div v-if="runs.length === 0" class="text-xs text-gray-400 italic py-6 text-center">
      No recent imports for this company.
    </div>
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <ImportCard
        v-for="run in runs"
        :key="run.name"
        :run="run"
        @click="emit('open', run)"
      />
    </div>
  </div>
</template>
