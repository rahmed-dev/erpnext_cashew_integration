<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue';
import { baseOption, mergeOption } from '@/charts/theme';

// vue-echarts AND the engine registration are both loaded lazily. echarts is
// ~160 kB gz even tree-shaken; a static import here would anchor it in whatever
// chunk imports CsChart and every route would pay for it at first paint. The
// `hasData` guard means the chunk is not even requested for an empty chart.
// This is also the ONLY place vue-echarts is referenced (C5.9) — swapping to a
// raw echarts.init stays a one-file change.
const VChart = defineAsyncComponent(async () => {
  const [chart, engine] = await Promise.all([
    import('vue-echarts'),
    import('@/charts/echarts'),
  ]);
  engine.registerECharts();
  return chart.default;
});

const props = defineProps({
  // Series, axes and formatters. Merged OVER the shared theme; arrays win
  // outright. Never a full option object built by a page — see theme.js.
  option: { type: Object, required: true },
  height: { type: [Number, String], default: 260 },
  loading: { type: Boolean, default: false },
  // False renders the empty state instead of an axis-less blank canvas.
  hasData: { type: Boolean, default: true },
  emptyText: { type: String, default: 'Nothing to plot for this period.' },
  ariaLabel: { type: String, default: '' },
});

const heightStyle = computed(() => ({
  height: typeof props.height === 'number' ? `${props.height}px` : props.height,
}));

// The accent shades are CSS custom properties rewritten in place by
// ThemeController when the user changes Cashew Settings.accent_color. That is an
// inline `style` mutation on <html>, which no reactive system observes — so
// watch it and rebuild the option. Same pattern the ApexCharts donut used.
const themeVersion = ref(0);
let observer = null;

onMounted(() => {
  if (typeof MutationObserver === 'undefined') return;
  observer = new MutationObserver(() => {
    themeVersion.value += 1;
  });
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ['style'] });
});

onBeforeUnmount(() => {
  observer?.disconnect();
  observer = null;
});

const merged = computed(() => {
  // Read so an accent change re-evaluates; the tokens themselves are read
  // inside the caller's option and in baseOption().
  void themeVersion.value;
  return mergeOption(baseOption(), props.option);
});
</script>

<template>
  <div class="relative w-full" :style="heightStyle">
    <div
      v-if="loading"
      class="h-full w-full animate-pulse rounded bg-gray-100"
      role="presentation"
    />

    <div
      v-else-if="!hasData"
      class="flex h-full w-full items-center justify-center px-4 text-center text-xs italic text-gray-400"
    >
      <slot name="empty">{{ emptyText }}</slot>
    </div>

    <VChart
      v-else
      class="h-full w-full"
      :option="merged"
      :aria-label="ariaLabel || undefined"
      autoresize
    />
  </div>
</template>
