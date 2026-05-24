<script setup>
import RunCard from './RunCard.vue';
import SkeletonBlock from '@/components/shared/SkeletonBlock.vue';

defineProps({
  rows: { type: Array, required: true },
  loading: { type: Boolean, default: false },
  pulseMap: { type: Object, default: () => ({}) },
});
const emit = defineEmits(['action']);
</script>

<template>
  <div class="space-y-2.5">
    <template v-if="loading && !rows.length">
      <SkeletonBlock v-for="i in 5" :key="`sk-${i}`" shape="block" height="92px" />
    </template>
    <template v-else>
      <RunCard
        v-for="row in rows"
        :key="row.name"
        :row="row"
        :pulse="!!pulseMap[row.name]"
        @action="(e) => emit('action', e)"
      />
    </template>
  </div>
</template>
