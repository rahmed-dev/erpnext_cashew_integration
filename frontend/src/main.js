import './index.css';
import { createApp } from 'vue';
import { resourcesPlugin, frappeRequest, setConfig } from 'frappe-ui';

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
// NOTE: no chart component is registered globally. A global registration is a
// static import into the entry chunk, which would pull the chart library into
// first paint on every route — including Imports and Settings, which draw no
// chart. <CsChart> (f012 c001) loads vue-echarts and the tree-shaken echarts
// registrations as an async component instead, so the engine downloads only when
// a chart with data actually mounts.

installErrorInterceptors();

app.mount('#app');

// c008 — open the Cashew Settings doc subscription for the SPA lifetime so
// accent_color edits in another tab repaint this one (D14).
subscribeSettings(() => {});

// c014 — register PWA service worker. SW is served by Frappe at
// /cashew/sw.js with Service-Worker-Allowed: /cashew/ so it can control
// the whole SPA scope (required for install prompt — start_url is /cashew/).
if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/cashew/sw.js', { scope: '/cashew/' })
      .catch((err) => console.warn('[cashew] SW register failed', err));
  });
}
