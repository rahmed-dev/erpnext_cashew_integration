import path from 'path';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import frappeui from 'frappe-ui/vite';
import { VitePWA } from 'vite-plugin-pwa';
import proxyOptions from './proxyOptions';

// frappe-ui's jinjaBootData spreads each key as a top-level window global,
// but the SPA reads window.boot.<key>. Inject a single window.boot object,
// AND swap the static theme-color content with a Jinja expression so the
// first paint already carries the user-chosen accent (no Indigo flash
// before ThemeController.init runs).
function cashewBootInjector() {
	return {
		name: 'cashew-boot-injector',
		transformIndexHtml(html, context) {
			if (context.server) return html;
			html = html.replace(
				/<meta name="theme-color"[^>]*>/,
				'<meta name="theme-color" content="{{ boot.theme_color }}" />',
			);
			return html.replace(
				/<\/body>/,
				`<script>window.boot = {{ boot | tojson }};</script></body>`,
			);
		},
	};
}

export default defineConfig({
	plugins: [
		cashewBootInjector(),
		frappeui({
			frappeProxy: false,
			jinjaBootData: false,
			lucideIcons: true,
			buildConfig: {
				outDir: '../cashew_integration/public/frontend',
				emptyOutDir: true,
				sourcemap: false,
				indexHtmlPath: '../cashew_integration/www/cashew.html',
				baseUrl: '/assets/cashew_integration/frontend/',
			},
		}),
		vue(),
		// c014: PWA — installable on mobile. SW emitted to outDir, served
		// under /cashew/sw.js by Frappe page renderer (so it scopes the SPA).
		// Manifest is served dynamically at /cashew/manifest.webmanifest by
		// the same renderer (theme_color tracks Cashew Settings.accent_color),
		// so VitePWA does NOT generate a static one (manifest: false).
		VitePWA({
			strategies: 'generateSW',
			registerType: 'autoUpdate',
			injectRegister: null,
			filename: 'sw.js',
			manifest: false,
			// Inline workbox runtime into sw.js. Otherwise SW (served from
			// /cashew/sw.js) tries to load `./workbox-*.js` relative to itself
			// — but that file lives at /assets/cashew_integration/frontend/.
			injectManifest: undefined,
			workbox: {
				// Self-contained SW (no separate workbox runtime file to fetch).
				inlineWorkboxRuntime: true,
				// Precache only hashed bundle assets. NEVER cashew.html — it is
				// Jinja-rendered each request (CSRF + window.boot must be fresh).
				globPatterns: ['**/*.{js,css,woff,woff2,png,svg,ico}'],
				globIgnores: ['**/*.html', 'manifest.webmanifest'],
				navigateFallback: null,
				// SW served from /cashew/, but precache assets live at
				// /assets/cashew_integration/frontend/. Rewrite all relative
				// precache URLs to absolute paths so workbox fetches the right
				// files regardless of SW location.
				modifyURLPrefix: {
					'': '/assets/cashew_integration/frontend/',
				},
				// Frappe site is single-origin; SW scope is /cashew/ so it only
				// intercepts SPA routes. Use NetworkFirst for navigations so the
				// freshly Jinja-rendered shell always wins when online.
				runtimeCaching: [
					{
						urlPattern: /^.*\/cashew\/.*$/,
						handler: 'NetworkFirst',
						options: {
							cacheName: 'cashew-spa-navigation',
							networkTimeoutSeconds: 5,
						},
					},
					{
						urlPattern: /^.*\/assets\/cashew_integration\/frontend\/.*$/,
						handler: 'StaleWhileRevalidate',
						options: { cacheName: 'cashew-assets' },
					},
				],
				clientsClaim: true,
				skipWaiting: true,
			},
		}),
	],
	server: {
		port: 8080,
		host: '0.0.0.0',
		proxy: proxyOptions,
	},
	resolve: {
		alias: {
			'@': path.resolve(__dirname, 'src'),
		},
	},
});
