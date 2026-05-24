import { createRouter, createWebHistory } from 'vue-router';

// SPA route base. Must match the `website_route_rules` prefix in hooks.py
// and the `redirect-to` in www/cashew.py. Change all three together if
// you ever rename the URL prefix.
export const SPA_BASE = '/cashew';

export const routes = [
  {
    path: '/',
    name: 'finance-dashboard',
    component: () => import('@/pages/FinanceDashboard.vue'),
    meta: { title: 'Dashboard' },
  },
  {
    path: '/runs',
    name: 'imports-list',
    component: () => import('@/pages/ImportsList.vue'),
    meta: { title: 'Imports' },
  },
  {
    path: '/runs/new',
    name: 'run-workspace-new',
    component: () => import('@/pages/RunWorkspace.vue'),
    meta: { title: 'New Import' },
  },
  {
    path: '/runs/:run_name',
    name: 'run-workspace',
    component: () => import('@/pages/RunWorkspace.vue'),
    meta: { title: 'Import Run' },
    props: true,
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('@/pages/Settings.vue'),
    meta: { title: 'Settings' },
  },
  {
    path: '/:catchAll(.*)',
    redirect: '/',
  },
];

const router = createRouter({
  history: createWebHistory(SPA_BASE),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition;
    return { top: 0 };
  },
});

export default router;
