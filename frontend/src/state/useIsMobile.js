import { ref } from 'vue';

const BREAKPOINT_MD = 768;
const isMobile = ref(false);

function update() {
  if (typeof window !== 'undefined') {
    isMobile.value = window.innerWidth < BREAKPOINT_MD;
  }
}

if (typeof window !== 'undefined') {
  update();
  window.addEventListener('resize', update);
}

export function useIsMobile() {
  return isMobile;
}
