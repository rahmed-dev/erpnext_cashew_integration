<script setup>
import AppSwitcher from './AppSwitcher.vue';
import NavItems from './NavItems.vue';
import UserChip from './UserChip.vue';
</script>

<template>
  <aside class="w-60 shrink-0 flex flex-col border-r border-gray-200 bg-white overflow-hidden">
    <AppSwitcher class="p-3 border-b border-gray-200 shrink-0" />
    <NavItems class="flex-1 p-2 overflow-y-auto" />
    <div class="border-t border-gray-200 p-3 shrink-0">
      <UserChip />
    </div>
  </aside>
</template>
