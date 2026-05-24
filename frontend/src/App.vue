<script setup>
import { onErrorCaptured } from 'vue';
import { toast } from 'frappe-ui';
import Sidebar from '@/components/Shell/Sidebar.vue';
import MobileTopBar from '@/components/Shell/MobileTopBar.vue';
import MobileBottomNav from '@/components/Shell/MobileBottomNav.vue';

onErrorCaptured((err, instance, info) => {
  // eslint-disable-next-line no-console
  console.error('[cashew] component error:', err, info, instance);
  toast.error(err?.message || String(err), { title: 'Something broke on this page' });
  return false;
});
</script>

<template>
  <div class="cashew-app h-screen flex overflow-hidden bg-gray-50 text-gray-900">
    <Sidebar class="hidden md:flex h-screen" />

    <div class="flex-1 flex flex-col min-w-0 h-screen">
      <MobileTopBar class="md:hidden shrink-0" />

      <main class="cashew-main flex-1 min-w-0 overflow-y-auto">
        <RouterView v-slot="{ Component }">
          <component :is="Component" />
        </RouterView>
      </main>
    </div>

    <MobileBottomNav class="md:hidden" />
  </div>
</template>

<style>
.cashew-main { padding-bottom: env(safe-area-inset-bottom); }
@media (max-width: 767px) {
  .cashew-main { padding-bottom: calc(60px + env(safe-area-inset-bottom)); }
}
</style>
