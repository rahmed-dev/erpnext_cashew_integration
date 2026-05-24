<script setup>
const props = defineProps({
  shape: { type: String, default: 'line' }, // line | block | circle | row
  width: { type: String, default: null },
  height: { type: String, default: null },
  lines: { type: Number, default: 1 },
});

function style(extra = {}) {
  const out = {};
  if (props.width) out.width = props.width;
  if (props.height) out.height = props.height;
  return { ...out, ...extra };
}
</script>

<template>
  <div v-if="shape === 'line'" class="space-y-2">
    <div
      v-for="i in lines"
      :key="i"
      class="cs-skel rounded-md"
      :style="style({ height: height || '12px', width: i === lines && lines > 1 ? '60%' : (width || '100%') })"
    />
  </div>
  <div
    v-else-if="shape === 'block'"
    class="cs-skel rounded-lg"
    :style="style({ height: height || '80px', width: width || '100%' })"
  />
  <div
    v-else-if="shape === 'circle'"
    class="cs-skel rounded-full"
    :style="style({ height: height || '32px', width: width || '32px' })"
  />
  <div v-else-if="shape === 'row'" class="flex items-center gap-3">
    <div class="cs-skel rounded-full h-7 w-7 shrink-0" />
    <div class="flex-1 space-y-1.5">
      <div class="cs-skel rounded h-3" style="width: 35%;" />
      <div class="cs-skel rounded h-3" style="width: 70%;" />
    </div>
  </div>
</template>

<style scoped>
.cs-skel {
  background: linear-gradient(90deg, #f3f4f6 0%, #e5e7eb 50%, #f3f4f6 100%);
  background-size: 200% 100%;
  animation: cs-shimmer 1.5s linear infinite;
}
@keyframes cs-shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
@media (prefers-reduced-motion: reduce) {
  .cs-skel { animation: none; }
}
</style>
