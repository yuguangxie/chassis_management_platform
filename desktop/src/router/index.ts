import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/overview' },
  { path: '/overview', component: () => import('../pages/OverviewPage.vue') },
  { path: '/network-config', component: () => import('../pages/NetworkConfigPage.vue') },
  { path: '/can-monitor', component: () => import('../pages/CanMonitorPage.vue') },
  { path: '/signal-dashboard', component: () => import('../pages/SignalDashboardPage.vue') },
  { path: '/realtime-curve', component: () => import('../pages/RealtimeCurvePage.vue') },
  { path: '/manual-control', component: () => import('../pages/ManualControlPage.vue') },
  { path: '/auto-test', component: () => import('../pages/AutoTestPage.vue') },
  { path: '/alarm-diagnosis', component: () => import('../pages/AlarmDiagnosisPage.vue') },
  { path: '/report-management', component: () => import('../pages/ReportManagementPage.vue') },
  { path: '/history', component: () => import('../pages/HistoryPage.vue') },
  { path: '/system-settings', component: () => import('../pages/SystemSettingsPage.vue') },
]

export default createRouter({
  history: createWebHashHistory(),
  routes,
})
