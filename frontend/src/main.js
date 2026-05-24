import './index.css';
import { createApp } from 'vue';
import { resourcesPlugin, frappeRequest, setConfig } from 'frappe-ui';
import VueApexCharts from 'vue3-apexcharts';

import App from './App.vue';
import router from './router';
import { ThemeController } from './theme';
import { installErrorInterceptors } from './errors';
import { subscribeSettings } from './realtime';

// Apply theme before mount — prevents flash of wrong accent.
ThemeController.init();

// Wire CSRF token from boot dict.
if (typeof window !== 'undefined') {
  const boot = window.boot || {};
  if (boot.csrf_token && !window.csrf_token) {
    window.csrf_token = boot.csrf_token;
  }
}

setConfig('resourceFetcher', frappeRequest);

router.afterEach((to) => {
  document.title = `${to.meta?.title || 'Cashew'} · Cashew`;
});

const app = createApp(App);
app.use(router);
app.use(resourcesPlugin);
app.component('apexchart', VueApexCharts);

installErrorInterceptors();

app.mount('#app');

// c008 — open the Cashew Settings doc subscription for the SPA lifetime so
// accent_color edits in another tab repaint this one (D14).
subscribeSettings(() => {});
