<script setup>
import { computed } from 'vue';
import { useRoute, RouterLink } from 'vue-router';
import { BarChart2, FileText, Settings as SettingsIcon } from 'lucide-vue-next';

const route = useRoute();
const ITEMS = [
  { to: '/',         icon: BarChart2,    label: 'Dashboard', match: (p) => p === '/' },
  { to: '/runs',     icon: FileText,     label: 'Imports',   match: (p) => p.startsWith('/runs') },
  { to: '/settings', icon: SettingsIcon, label: 'Settings',  match: (p) => p.startsWith('/settings') },
];
function isActive(item) { return item.match(route.path); }
</script>

<template>
  <nav
    aria-label="Primary"
    class="fixed bottom-0 inset-x-0 h-14 bg-white border-t border-gray-200 flex items-stretch z-30"
    style="padding-bottom: env(safe-area-inset-bottom);"
  >
    <RouterLink
      v-for="item in ITEMS"
      :key="item.to"
      :to="item.to"
      class="flex-1 flex flex-col items-center justify-center gap-0.5 text-[11px]"
      :class="isActive(item) ? 'text-cs-accent-700 font-semibold' : 'text-gray-600'"
      :aria-current="isActive(item) ? 'page' : undefined"
    >
      <component :is="item.icon" :size="20" />
      <span>{{ item.label }}</span>
    </RouterLink>
  </nav>
</template>
