import { ref } from 'vue';
import { useDefaultPeriod } from '@/boot';

const defaults = useDefaultPeriod();
const period = ref({ start: defaults.start, end: defaults.end });

export function useDashboardPeriod() {
  return {
    period,
    setPeriod(next) { period.value = { ...next }; },
    reset() { period.value = { start: defaults.start, end: defaults.end }; },
  };
}
