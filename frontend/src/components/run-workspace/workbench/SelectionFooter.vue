<script setup>
import { computed } from 'vue';
import { Button } from 'frappe-ui';

const props = defineProps({
  count: { type: Number, default: 0 },
  actions: { type: Array, default: () => [] },
  busy: { type: [String, null], default: null },
});
const emit = defineEmits(['action', 'clear']);

const visible = computed(() => props.count > 0);
</script>

<template>
  <Transition name="slide-up">
    <div v-if="visible" class="fixed left-0 right-0 bottom-16 md:bottom-4 px-4 z-30 pointer-events-none">
      <div class="mx-auto max-w-2xl pointer-events-auto rounded-full bg-gray-900 text-white px-3 py-2 flex items-center gap-2 shadow-lg">
        <span class="text-sm pl-2">{{ count }} selected</span>
        <span class="flex-1" />
        <Button
          v-for="a in actions"
          :key="a.id"
          variant="ghost"
          theme="gray"
          :class="'!text-white hover:!bg-white/10'"
          :loading="busy === a.id"
          :disabled="!!busy"
          @click="emit('action', a)"
        >
          {{ a.label }}
        </Button>
        <Button
          variant="ghost"
          :class="'!text-white hover:!bg-white/10'"
          @click="emit('clear')"
        >
          Clear
        </Button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.slide-up-enter-from, .slide-up-leave-to { transform: translateY(120%); opacity: 0; }
.slide-up-enter-active, .slide-up-leave-active { transition: all 200ms ease-out; }
</style>
