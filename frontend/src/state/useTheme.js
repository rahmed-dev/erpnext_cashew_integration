import { ref } from 'vue';
import { useCashewSettings } from '@/boot';
import { ThemeController } from '@/theme';

const seed = useCashewSettings();
const currentPreset = ref(seed.accent_color || 'Indigo');
const currentCustomHex = ref(seed.accent_color_custom || null);

export function useTheme() {
  return {
    currentPreset,
    currentCustomHex,
    setTheme(preset, customHex = null) {
      currentPreset.value = preset;
      currentCustomHex.value = customHex;
      ThemeController.apply(preset, customHex);
    },
  };
}
