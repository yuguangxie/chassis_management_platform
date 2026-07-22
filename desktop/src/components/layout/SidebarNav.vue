<template>
  <aside class="sidebar" :aria-hidden="layout.sidebarCollapsed">
    <div class="brand">
      <div class="logo"><Truck :size="25" /></div>
      <div class="brand-copy">
        <strong>低速无人车线控底盘</strong>
        <span>生产下线管理平台</span>
      </div>
    </div>

    <nav class="nav-list">
      <RouterLink v-for="item in visibleNav" :key="item.path" :to="item.path" class="nav-item">
        <component :is="item.icon" :size="20" />
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="session-panel">
      <div><strong>{{ auth.principal?.username }}</strong><span>{{ auth.principal?.role }}</span></div>
      <button type="button" title="锁定工作站" aria-label="锁定工作站" @click="lockSession"><LockKeyhole :size="16" /></button>
      <button type="button" title="退出登录" aria-label="退出登录" @click="logout"><LogOut :size="16" /></button>
    </div>

    <button
      class="collapse"
      type="button"
      aria-label="隐藏左侧导航栏"
      title="隐藏左侧导航栏"
      @click="layout.collapseSidebar"
    >
      <ChevronsLeft :size="18" />
      <span>收起侧栏</span>
    </button>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Activity,
  ChevronsLeft,
  FileText,
  Gamepad2,
  Gauge,
  Globe2,
  History,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  Monitor,
  Settings,
  TriangleAlert,
  Truck,
  Zap,
} from 'lucide-vue-next'
import { useLayoutStore } from '../../stores/layout'
import { useAuthStore, type Role } from '../../stores/auth'

const layout = useLayoutStore()
const auth = useAuthStore()
const router = useRouter()

const nav = [
  { path: '/overview', label: '总览', icon: LayoutDashboard, roles: ['viewer','operator','engineer','admin'] as Role[] },
  { path: '/network-config', label: '网络配置', icon: Globe2, roles: ['engineer','admin'] as Role[] },
  { path: '/can-monitor', label: 'CAN监控', icon: Monitor, roles: ['viewer','operator','engineer','admin'] as Role[] },
  { path: '/signal-dashboard', label: '信号仪表盘', icon: Gauge, roles: ['viewer','operator','engineer','admin'] as Role[] },
  { path: '/realtime-curve', label: '实时曲线', icon: Activity, roles: ['viewer','operator','engineer','admin'] as Role[] },
  { path: '/manual-control', label: '手动控制', icon: Gamepad2, roles: ['engineer','admin'] as Role[] },
  { path: '/auto-test', label: '一键检测', icon: Zap, roles: ['operator','engineer','admin'] as Role[] },
  { path: '/alarm-diagnosis', label: '告警诊断', icon: TriangleAlert, roles: ['viewer','operator','engineer','admin'] as Role[] },
  { path: '/report-management', label: '报告管理', icon: FileText, roles: ['viewer','operator','engineer','admin'] as Role[] },
  { path: '/history', label: '历史记录', icon: History, roles: ['viewer','operator','engineer','admin'] as Role[] },
  { path: '/system-settings', label: '系统设置', icon: Settings, roles: ['engineer','admin'] as Role[] },
]
const visibleNav = computed(() => nav.filter((item) => auth.hasAnyRole(item.roles)))

async function lockSession() {
  await auth.lock()
  await router.push('/lock')
}

async function logout() {
  await auth.logout()
  await router.push('/login')
}
</script>

<style scoped>
.sidebar {
  position: relative;
  width: var(--shell-sidebar-width, var(--sidebar-width));
  min-width: var(--shell-sidebar-width, var(--sidebar-width));
  height: 100vh;
  background:
    linear-gradient(180deg, rgba(14, 35, 61, .96), rgba(7, 17, 31, 1) 48%, rgba(5, 13, 24, 1)),
    #0A1628;
  border-right: 1px solid #1E3A5F;
  box-shadow: inset -1px 0 0 rgba(47, 128, 255, .06);
  padding: 18px 14px 16px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  opacity: 1;
  transition: width 220ms ease-in-out, min-width 220ms ease-in-out, opacity 160ms ease-in-out, padding 220ms ease-in-out, border-color 160ms ease-in-out;
}

.session-panel{display:grid;grid-template-columns:minmax(0,1fr) 30px 30px;gap:6px;align-items:center;margin-top:auto;margin-bottom:8px;padding:9px;border:1px solid rgba(47,128,255,.24);border-radius:7px;background:rgba(7,17,31,.5)}
.session-panel div{min-width:0;display:flex;flex-direction:column}.session-panel strong,.session-panel span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.session-panel strong{font-size:12px;color:#eaf2ff}.session-panel span{font-size:10px;color:#8fa5c4}.session-panel button{width:30px;height:30px;display:grid;place-items:center;border:1px solid #294b72;border-radius:5px;background:#0a1b30;color:#9cc8ff}


.brand {
  min-height: 82px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 10px 17px;
  border-bottom: 1px solid rgba(30, 58, 95, .92);
  margin-bottom: 16px;
}

.logo {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 1px solid rgba(47, 128, 255, .72);
  display: grid;
  place-items: center;
  color: #A9D1FF;
  background: radial-gradient(circle at 35% 25%, rgba(47, 128, 255, .42), rgba(9, 33, 60, .96));
  box-shadow: 0 0 22px rgba(47, 128, 255, .24), inset 0 0 18px rgba(47, 128, 255, .12);
  flex: 0 0 auto;
}

.brand-copy {
  min-width: 0;
}

.brand-copy strong,
.brand-copy span {
  display: block;
  line-height: 1.3;
  white-space: nowrap;
}

.brand-copy strong {
  color: #EEF6FF;
  font-size: 16px;
  font-weight: 750;
}

.brand-copy span {
  color: #9FB3D0;
  font-size: 13px;
  margin-top: 5px;
}

.nav-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-height: 0;
}

.nav-item {
  position: relative;
  height: 48px;
  color: #BFD0E8;
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 16px;
  border-radius: 8px;
  border: 1px solid transparent;
  transition: background .16s ease, border-color .16s ease, color .16s ease;
}

.nav-item svg {
  color: #8EA7C8;
  flex: 0 0 auto;
}

.nav-item span {
  font-size: 15px;
  font-weight: 600;
}

.nav-item:hover {
  color: #FFFFFF;
  background: rgba(16, 36, 61, .9);
  border-color: rgba(47, 128, 255, .18);
}

.nav-item.router-link-active {
  color: #FFFFFF;
  background: linear-gradient(90deg, rgba(47, 128, 255, .96), rgba(21, 73, 137, .82));
  border-color: rgba(82, 158, 255, .65);
  box-shadow: 0 10px 22px rgba(47, 128, 255, .18), inset 3px 0 0 #9CCBFF;
}

.nav-item.router-link-active svg {
  color: #FFFFFF;
}

.collapse {
  margin-top: 0;
  height: 46px;
  border: 1px solid rgba(30, 58, 95, .86);
  border-radius: 8px;
  background: rgba(10, 22, 40, .78);
  color: #93A7C5;
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
}

.collapse:hover {
  color: #EAF2FF;
  border-color: rgba(47, 128, 255, .44);
}

@media (max-height: 840px) {
  .sidebar { padding-top: 12px; }
  .brand { min-height: 68px; margin-bottom: 10px; padding-bottom: 12px; }
  .nav-list { gap: 4px; }
  .nav-item { height: 40px; }
}
</style>
