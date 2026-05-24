import { ref } from 'vue';

// 'connected' | 'reconnecting' | 'disconnected' | 'unknown'
const status = ref('unknown');

export function useRealtimeStatus() {
  return status;
}

export function setRealtimeStatus(next) {
  status.value = next;
}
