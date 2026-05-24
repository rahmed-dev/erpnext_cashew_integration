<script setup>
import { Landmark } from 'lucide-vue-next';
</script>

<template>
  <header class="h-12 flex items-center px-4 border-b border-gray-200 bg-white">
    <div class="flex items-center gap-2">
      <span class="h-7 w-7 rounded-md bg-cs-accent-50 text-cs-accent flex items-center justify-center">
        <Landmark :size="16" />
      </span>
      <span class="text-sm font-semibold">Cashew</span>
    </div>
  </header>
</template>
