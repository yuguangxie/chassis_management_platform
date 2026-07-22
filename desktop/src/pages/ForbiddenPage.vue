<template>
  <main class="forbidden-page"><section><ShieldX :size="52" /><h1>403</h1><h2>当前身份无权访问此页面</h2><p>页面可见性来自后端 principal；直接调用 API 仍会执行独立鉴权。</p><button @click="router.replace('/overview')">返回总览</button></section></main>
</template>
<script setup lang="ts">
import { ShieldX } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
const router=useRouter()
</script>
<style scoped>
.forbidden-page{width:100vw;height:100vh;display:grid;place-items:center;background:#07111f;color:#eaf2ff;text-align:center}section{max-width:520px;padding:42px;border:1px solid #4b2938;border-radius:12px;background:#101b2d}svg,h1{color:#ef4444}h1{font-size:44px;margin:12px 0 0}h2{margin:4px 0 12px}p{color:#96abc7}button{margin-top:22px;height:40px;padding:0 24px;border:1px solid #2f80ff;border-radius:6px;background:#0d56b5;color:#fff}
</style>
