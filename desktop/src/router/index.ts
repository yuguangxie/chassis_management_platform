import { createRouter, createWebHashHistory, type RouteRecordRaw, type RouterHistory } from 'vue-router'
import { useAuthStore, type Role } from '../stores/auth'

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    roles?: Role[]
    publicLayout?: boolean
  }
}

export const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/overview' },
  { path: '/login', component: () => import('../pages/LoginPage.vue'), meta: { publicLayout: true } },
  { path: '/lock', component: () => import('../pages/LockScreenPage.vue'), meta: { publicLayout: true } },
  { path: '/forbidden', component: () => import('../pages/ForbiddenPage.vue'), meta: { publicLayout: true } },
  { path: '/overview', component: () => import('../pages/OverviewPage.vue'), meta: { requiresAuth: true, roles: ['viewer', 'operator', 'engineer', 'admin'] } },
  { path: '/network-config', component: () => import('../pages/NetworkConfigPage.vue'), meta: { requiresAuth: true, roles: ['engineer', 'admin'] } },
  { path: '/can-monitor', component: () => import('../pages/CanMonitorPage.vue'), meta: { requiresAuth: true, roles: ['viewer', 'operator', 'engineer', 'admin'] } },
  { path: '/signal-dashboard', component: () => import('../pages/SignalDashboardPage.vue'), meta: { requiresAuth: true, roles: ['viewer', 'operator', 'engineer', 'admin'] } },
  { path: '/realtime-curve', component: () => import('../pages/RealtimeCurvePage.vue'), meta: { requiresAuth: true, roles: ['viewer', 'operator', 'engineer', 'admin'] } },
  { path: '/manual-control', component: () => import('../pages/ManualControlPage.vue'), meta: { requiresAuth: true, roles: ['engineer', 'admin'] } },
  { path: '/auto-test', component: () => import('../pages/AutoTestPage.vue'), meta: { requiresAuth: true, roles: ['operator', 'engineer', 'admin'] } },
  { path: '/alarm-diagnosis', component: () => import('../pages/AlarmDiagnosisPage.vue'), meta: { requiresAuth: true, roles: ['viewer', 'operator', 'engineer', 'admin'] } },
  { path: '/report-management', component: () => import('../pages/ReportManagementPage.vue'), meta: { requiresAuth: true, roles: ['viewer', 'operator', 'engineer', 'admin'] } },
  { path: '/history', component: () => import('../pages/HistoryPage.vue'), meta: { requiresAuth: true, roles: ['viewer', 'operator', 'engineer', 'admin'] } },
  { path: '/system-settings', component: () => import('../pages/SystemSettingsPage.vue'), meta: { requiresAuth: true, roles: ['engineer', 'admin'] } },
]

export function createAppRouter(history: RouterHistory = createWebHashHistory()) {
  const appRouter = createRouter({ history, routes })
  appRouter.beforeEach(async (to) => {
    const auth = useAuthStore()
    await auth.initialize()
    if (to.meta.requiresAuth && !auth.authenticated) {
      return {
        path: auth.lockedUsername ? '/lock' : '/login',
        query: { redirect: to.fullPath, ...(auth.expired ? { reason: 'expired' } : {}) },
      }
    }
    if (to.meta.roles?.length && !auth.hasAnyRole(to.meta.roles)) {
      return { path: '/forbidden', query: { from: to.fullPath } }
    }
    if (to.path === '/login' && auth.authenticated) return '/overview'
    return true
  })
  return appRouter
}

export default createAppRouter()
