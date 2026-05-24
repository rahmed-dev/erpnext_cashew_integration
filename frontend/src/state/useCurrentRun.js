import { computed } from 'vue';
import { useRoute } from 'vue-router';

export function useCurrentRun() {
  const route = useRoute();
  return computed(() => {
    if (route.name === 'run-workspace') return route.params.run_name;
    return null;
  });
}
