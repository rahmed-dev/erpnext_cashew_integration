<script setup>
import { useRouter } from 'vue-router';
import { Button } from 'frappe-ui';
import { Inbox, FileSearch, Database, Sparkles } from 'lucide-vue-next';

const props = defineProps({
  illustration: { type: String, default: 'no-data' }, // empty-list | no-data | empty-results | first-run
  title: { type: String, required: true },
  body: { type: String, default: null },
  primary: { type: Object, default: null },   // { label, action: () => void | string }
  secondary: { type: Object, default: null },
});

const ICONS = {
  'empty-list':    Inbox,
  'no-data':       Database,
  'empty-results': FileSearch,
  'first-run':     Sparkles,
};

const router = useRouter();
function run(item) {
  if (!item?.action) return;
  if (typeof item.action === 'string') router.push(item.action);
  else item.action();
}
</script>

<template>
  <div class="flex flex-col items-center text-center py-16 px-6">
    <span class="h-16 w-16 rounded-full bg-cs-accent-50 text-cs-accent flex items-center justify-center mb-4">
      <component :is="ICONS[illustration] || Database" :size="28" />
    </span>
    <h2 class="text-lg font-semibold text-gray-900">{{ title }}</h2>
    <p v-if="body" class="text-sm text-gray-600 mt-1 max-w-md">{{ body }}</p>
    <div v-if="primary || secondary" class="flex items-center gap-2 mt-5">
      <Button v-if="primary" variant="solid" theme="accent" @click="run(primary)">{{ primary.label }}</Button>
      <Button v-if="secondary" variant="ghost" @click="run(secondary)">{{ secondary.label }}</Button>
    </div>
  </div>
</template>
