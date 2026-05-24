<script setup>
import { useRouter } from 'vue-router';
import { ChevronLeft } from 'lucide-vue-next';

const props = defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: null },
  backRoute: { type: String, default: null },
  border: { type: Boolean, default: true },
});

const router = useRouter();
function goBack() {
  if (props.backRoute) router.push(props.backRoute);
}
</script>

<template>
  <header
    :class="[
      'flex flex-wrap items-center gap-3 py-4',
      border ? 'border-b border-gray-200 mb-4' : '',
    ]"
  >
    <button
      v-if="backRoute"
      type="button"
      class="h-8 w-8 rounded-md hover:bg-gray-100 flex items-center justify-center text-gray-600"
      :aria-label="`Back to ${backRoute}`"
      @click="goBack"
    >
      <ChevronLeft :size="18" />
    </button>
    <div class="flex-1 min-w-0">
      <h1 class="text-[24px] leading-tight font-semibold tracking-[-0.01em] truncate">{{ title }}</h1>
      <p v-if="subtitle" class="text-[13px] text-gray-500 mt-0.5">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.meta" class="flex items-center gap-2 order-2 md:order-none">
      <slot name="meta" />
    </div>
    <div v-if="$slots.actions" class="flex items-center gap-2 ml-auto">
      <slot name="actions" />
    </div>
  </header>
</template>
