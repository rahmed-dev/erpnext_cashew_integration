<script setup>
import StatusPill from '@/components/shared/StatusPill.vue';
import DateRange from '@/components/shared/DateRange.vue';

defineProps({
  run: { type: Object, required: true },
});
</script>

<template>
  <button
    type="button"
    class="text-left rounded-lg border border-gray-200 hover:border-[var(--cs-accent)] hover:shadow-sm transition p-3 bg-white"
    @click="$emit('click')"
  >
    <div class="flex items-center justify-between gap-2 mb-1.5">
      <span class="font-mono text-xs text-gray-700 truncate min-w-0">{{ run.name }}</span>
      <StatusPill kind="run-status" :value="run.status" />
    </div>
    <div class="text-xs text-gray-500 truncate">
      <DateRange :start="run.period_start" :end="run.period_end" />
    </div>
    <div class="flex items-center gap-3 mt-2 text-[11px] text-gray-500">
      <span><span class="text-gray-900 font-medium">{{ run.rows_total || 0 }}</span> rows</span>
      <span v-if="run.rows_failed"><span class="text-red-700 font-medium">{{ run.rows_failed }}</span> failed</span>
      <span v-if="run.rows_posted"><span class="text-green-700 font-medium">{{ run.rows_posted }}</span> posted</span>
    </div>
  </button>
</template>
