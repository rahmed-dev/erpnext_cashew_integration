<script setup>
import { useRealtimeStatus } from '@/state/useRealtimeStatus';

defineProps({ compact: Boolean });
const status = useRealtimeStatus();

const palette = {
  connected:    { dot: 'bg-green-500',               label: 'Live' },
  reconnecting: { dot: 'bg-amber-500 animate-pulse', label: 'Reconnecting…' },
  disconnected: { dot: 'bg-red-500',                 label: 'Polling (30s)' },
  unknown:      { dot: 'bg-gray-300',                label: '—' },
};
</script>

<template>
  <div
    class="flex items-center gap-2 text-xs text-gray-600"
    :aria-label="`Realtime status: ${palette[status].label}`"
  >
    <span :class="['w-2 h-2 rounded-full', palette[status].dot]" />
    <span v-if="!compact">{{ palette[status].label }}</span>
  </div>
</template>
