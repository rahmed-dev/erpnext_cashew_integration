<script setup>
import { computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import RunHeader from '@/components/run-workspace/RunHeader.vue';
import StateStepper from '@/components/run-workspace/StateStepper.vue';
import UploadSection from '@/components/run-workspace/sections/UploadSection.vue';
import PreviewSection from '@/components/run-workspace/sections/PreviewSection.vue';
import RowsWorkbench from '@/components/run-workspace/sections/RowsWorkbench.vue';
import CompletedSummary from '@/components/run-workspace/sections/CompletedSummary.vue';
import SkeletonBlock from '@/components/shared/SkeletonBlock.vue';
import EmptyState from '@/components/shared/EmptyState.vue';

import { useRun } from '@/composables/useRun';
import { useRunRealtime } from '@/composables/useRunRealtime';

const route = useRoute();
const router = useRouter();

const runName = computed(() => route.params.run_name || null);
const { doc, rows, loading, error, reload, patchDoc, patchRow } = useRun(runName);

watch(runName, () => { reload(); }, { immediate: true });

useRunRealtime(runName, { patchDoc, patchRow });

const status = computed(() => doc.value?.status || (runName.value ? null : 'Draft'));

const sectionComponent = computed(() => {
  if (!runName.value || status.value === 'Draft') return UploadSection;
  if (status.value === 'Parsed') return PreviewSection;
  if (['Validated', 'Queued', 'Processing'].includes(status.value)) return RowsWorkbench;
  if (['Completed', 'Failed', 'Cancelled', 'Reverting', 'Reverted', 'Revert-Failed'].includes(status.value)) return CompletedSummary;
  return UploadSection;
});

function onParsed(newName) {
  router.replace(`/runs/${newName}`);
}
</script>

<template>
  <div class="flex flex-col">
    <RunHeader :doc="doc" :run-name="runName" :loading="loading" @reload="reload" />
    <StateStepper :status="status" />

    <div class="px-4 py-4 max-w-7xl mx-auto w-full">
      <SkeletonBlock v-if="loading && !doc && runName" class="h-96" />
      <EmptyState
        v-else-if="error && runName"
        illustration="no-data"
        title="Couldn't load this run."
        body="It may have been deleted or you don't have permission to view it."
        :primary="{ label: 'Back to Imports', action: '/runs' }"
      />
      <component
        v-else
        :is="sectionComponent"
        :doc="doc || {}"
        :rows="rows"
        :run-name="runName"
        @reload="reload"
        @parsed="onParsed"
      />
    </div>
  </div>
</template>
