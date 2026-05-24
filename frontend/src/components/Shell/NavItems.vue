<script setup>
import { computed } from 'vue';
import { useRoute, RouterLink } from 'vue-router';
import { BarChart2, FileText, Settings as SettingsIcon } from 'lucide-vue-next';
import { hasWriteSettings } from '@/boot';

const route = useRoute();
const showSettings = computed(() => true); // shell shows it; page enforces read-only.

const ITEMS = [
  { to: '/',        icon: BarChart2,    label: 'Dashboard', match: (p) => p === '/' },
  { to: '/runs',    icon: FileText,     label: 'Imports',   match: (p) => p.startsWith('/runs') },
  { to: '/settings', icon: SettingsIcon, label: 'Settings',  match: (p) => p.startsWith('/settings') },
];

function isActive(item) {
  return item.match(route.path);
}
</script>

<template>
  <nav aria-label="Primary">
    <ul class="space-y-1">
      <li v-for="item in ITEMS" :key="item.to">
        <RouterLink
          :to="item.to"
          class="group flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors"
          :class="isActive(item)
            ? 'bg-cs-accent-50 text-cs-accent-700 font-semibold'
            : 'text-gray-700 hover:bg-gray-50'"
          :aria-current="isActive(item) ? 'page' : undefined"
        >
          <component :is="item.icon" :size="18" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </li>
    </ul>
  </nav>
</template>
