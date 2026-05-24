import path from 'path';
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import frappeui from 'frappe-ui/vite';
import proxyOptions from './proxyOptions';

// frappe-ui's jinjaBootData spreads each key as a top-level window global,
// but the SPA reads window.boot.<key>. Inject a single window.boot object instead.
function cashewBootInjector() {
	return {
		name: 'cashew-boot-injector',
		transformIndexHtml(html, context) {
			if (context.server) return html;
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
