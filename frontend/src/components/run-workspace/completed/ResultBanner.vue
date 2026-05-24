<script setup>
import { computed } from 'vue';
import { CheckCircle2, XCircle, Undo2, AlertTriangle } from 'lucide-vue-next';

const props = defineProps({
  doc: { type: Object, required: true },
});

const META = {
  Completed:      { tone: 'green', Icon: CheckCircle2, prefix: '✓ Completed' },
  Failed:         { tone: 'red',   Icon: XCircle,      prefix: '⨯ Failed'    },
  Cancelled:      { tone: 'amber', Icon: AlertTriangle, prefix: '⊘ Cancelled' },
  Reverting:      { tone: 'amber', Icon: Undo2,        prefix: '↺ Reverting' },
  Reverted:       { tone: 'amber', Icon: Undo2,        prefix: '↺ Reverted'  },
  'Revert-Failed':{ tone: 'red',   Icon: XCircle,      prefix: '⨯ Revert failed' },
};

const meta = computed(() => META[props.doc?.status] || { tone: 'gray', Icon: AlertTriangle, prefix: props.doc?.status });

const subtitle = computed(() => {
  const s = props.doc?.started_on;
  const f = props.doc?.finished_on;
  if (!s || !f) return null;
  const fmt = (v) => v ? new Date(v).toLocaleString() : '—';
  return `Started ${fmt(s)} · Finished ${fmt(f)}`;
});

const title = computed(() => {
  const d = props.doc || {};
  const posted = d.rows_posted ?? 0;
  const failed = d.rows_failed ?? 0;
  if (d.status === 'Completed') return `${meta.value.prefix} — ${posted} rows posted${failed ? `, ${failed} failed` : ''}`;
  if (d.status === 'Reverted') return `${meta.value.prefix} — ${posted} posted documents reversed`;
  return `${meta.value.prefix}`;
});

const toneClass = computed(() => ({
  green: 'border-green-200 bg-green-50 text-green-900',
  red: 'border-red-200 bg-red-50 text-red-900',
  amber: 'border-amber-200 bg-amber-50 text-amber-900',
  gray: 'border-gray-200 bg-gray-50 text-gray-900',
}[meta.value.tone]));
</script>

<template>
  <div :class="['rounded-lg border px-4 py-3 flex items-start gap-3', toneClass]">
    <component :is="meta.Icon" :size="20" class="mt-0.5 shrink-0" />
    <div>
      <div class="text-sm font-semibold">{{ title }}</div>
      <div v-if="subtitle" class="text-xs opacity-80 mt-0.5">{{ subtitle }}</div>
    </div>
  </div>
</template>
