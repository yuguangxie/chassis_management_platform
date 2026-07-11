<template>
  <div class="shell">
    <SidebarNav />
    <main class="main">
      <WindowChrome />
      <TopStatusBar />
      <section class="content"><RouterView /></section>
    </main>
  </div>
</template>
<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import { useAppStatusStore } from '../../stores/appStatus'
import SidebarNav from './SidebarNav.vue'
import TopStatusBar from './TopStatusBar.vue'
import WindowChrome from './WindowChrome.vue'
const store = useAppStatusStore()
let refreshTimer: number | undefined
onMounted(() => { void store.refresh(); store.connectWs(); refreshTimer = window.setInterval(() => void store.refresh(), 3000) })
onBeforeUnmount(() => { if (refreshTimer) window.clearInterval(refreshTimer) })
</script>
<style scoped>
.shell{display:flex;height:100vh;overflow:hidden;background:var(--bg-page)}.main{margin-left:var(--sidebar-width);width:calc(100vw - var(--sidebar-width));height:100vh;display:flex;flex-direction:column;min-width:0}.content{height:calc(100vh - var(--chrome-height) - var(--topbar-height));min-height:0;overflow:hidden;padding:12px;background:radial-gradient(circle at 30% -10%,rgba(47,128,255,.14),transparent 34%),var(--bg-page)}
.content::-webkit-scrollbar{width:10px;height:10px}.content::-webkit-scrollbar-thumb{background:#16365A;border-radius:999px;border:2px solid #07111F}.content::-webkit-scrollbar-track{background:#07111F}
</style>
