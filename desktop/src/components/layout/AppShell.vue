<template>
  <div :class="['shell', { 'sidebar-collapsed': layout.sidebarCollapsed }]">
    <SidebarNav />
    <main class="main">
      <WindowChrome />
      <TopStatusBar />
      <section class="content"><RouterView /></section>
    </main>
    <button
      v-if="layout.sidebarCollapsed"
      class="sidebar-expand"
      type="button"
      aria-label="展开侧栏"
      title="展开侧栏"
      @click="layout.expandSidebar"
    >
      <ChevronsRight :size="18" />
    </button>
  </div>
</template>
<script setup lang="ts">
import { onBeforeUnmount, onMounted, watch } from 'vue'
import { ChevronsRight } from 'lucide-vue-next'
import { useAppStatusStore } from '../../stores/appStatus'
import { useLayoutStore } from '../../stores/layout'
import SidebarNav from './SidebarNav.vue'
import TopStatusBar from './TopStatusBar.vue'
import WindowChrome from './WindowChrome.vue'
const store = useAppStatusStore()
const layout = useLayoutStore()
let refreshTimer: number | undefined
let layoutTimer: number | undefined

function handleKeydown(event: KeyboardEvent) {
  if (!event.ctrlKey || event.altKey || event.shiftKey || event.key.toLowerCase() !== 'b') return
  const target = event.target as HTMLElement | null
  if (target?.matches('input, textarea, select, [contenteditable="true"]')) return
  event.preventDefault()
  layout.toggleSidebar()
}

watch(() => layout.sidebarCollapsed, () => {
  if (layoutTimer) window.clearTimeout(layoutTimer)
  layoutTimer = window.setTimeout(() => {
    window.dispatchEvent(new Event('resize'))
    window.dispatchEvent(new Event('chassis:sidebar-transition-end'))
  }, 230)
})

onMounted(() => {
  void store.refresh()
  store.connectWs()
  refreshTimer = window.setInterval(() => void store.refresh(), 3000)
  window.addEventListener('keydown', handleKeydown)
})

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
  if (layoutTimer) window.clearTimeout(layoutTimer)
  window.removeEventListener('keydown', handleKeydown)
})
</script>
<style scoped>
.shell{--shell-sidebar-width:var(--sidebar-width);position:relative;display:grid;grid-template-columns:var(--shell-sidebar-width) minmax(0,1fr);width:100vw;height:100vh;overflow:hidden;background:var(--bg-page);transition:grid-template-columns 220ms ease-in-out}.shell.sidebar-collapsed{--shell-sidebar-width:0px}.main{grid-column:2;min-width:0;min-height:0;height:100vh;display:flex;flex-direction:column;overflow:hidden}.content{height:calc(100vh - var(--chrome-height) - var(--topbar-height));min-width:0;min-height:0;overflow:hidden;padding:10px 12px 12px;background:radial-gradient(circle at 30% -10%,rgba(47,128,255,.14),transparent 34%),var(--bg-page)}
.content::-webkit-scrollbar{width:10px;height:10px}.content::-webkit-scrollbar-thumb{background:#16365A;border-radius:999px;border:2px solid #07111F}.content::-webkit-scrollbar-track{background:#07111F}
.shell.sidebar-collapsed :deep(.sidebar){width:0!important;min-width:0!important;padding-inline:0!important;border-right-width:0!important;opacity:0;pointer-events:none}
.sidebar-expand{position:fixed;left:0;top:50%;z-index:60;width:32px;height:58px;display:grid;place-items:center;border:1px solid rgba(47,128,255,.68);border-left:0;border-radius:0 7px 7px 0;color:#B9D9FF;background:rgba(10,31,56,.94);box-shadow:4px 6px 18px rgba(0,0,0,.28);transform:translateY(-50%);transition:background .16s ease,border-color .16s ease,color .16s ease;-webkit-app-region:no-drag}.sidebar-expand:hover{border-color:#4C95FF;color:#FFFFFF;background:#123A68}
</style>
