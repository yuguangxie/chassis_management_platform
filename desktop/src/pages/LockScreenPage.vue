<template>
  <main class="auth-page">
    <section class="auth-card">
      <LockKeyhole :size="42" />
      <h1>工作站已锁定</h1>
      <p>{{ auth.lockedUsername || '当前用户' }}</p>
      <form @submit.prevent="unlock">
        <input v-model="password" type="password" autocomplete="current-password" placeholder="输入密码解锁" required minlength="12" />
        <span v-if="error">{{ error }}</span>
        <button type="submit" :disabled="loading">{{ loading ? '验证中…' : '解锁' }}</button>
        <button class="secondary" type="button" @click="switchUser">切换用户</button>
      </form>
    </section>
  </main>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LockKeyhole } from 'lucide-vue-next'
import { formatApiError } from '../api/http'
import { useAuthStore } from '../stores/auth'
const auth=useAuthStore();const route=useRoute();const router=useRouter();const password=ref('');const error=ref('');const loading=ref(false)
async function unlock(){if(!auth.lockedUsername){await switchUser();return}loading.value=true;error.value='';try{await auth.unlock(auth.lockedUsername,password.value);const target=typeof route.query.redirect==='string'&&route.query.redirect.startsWith('/')?route.query.redirect:'/overview';await router.replace(target)}catch(cause){error.value=formatApiError(cause)}finally{loading.value=false}}
async function switchUser(){auth.clearSession(true);await router.replace('/login')}
</script>
<style scoped>
.auth-page{width:100vw;height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 50% 0,rgba(47,128,255,.2),transparent 38%),#07111f;color:#eaf2ff}.auth-card{width:min(390px,calc(100vw - 32px));padding:38px;text-align:center;border:1px solid #1e3a5f;border-radius:12px;background:#0b1b30;box-shadow:0 24px 70px rgba(0,0,0,.42)}svg{color:#8fc4ff}h1{margin:16px 0 8px}p{color:#8fa5c4}form{display:grid;gap:12px;margin-top:25px}input,button{height:41px;border-radius:6px}input{padding:0 12px;border:1px solid #294b72;background:#071525;color:#fff}button{border:1px solid #4b98ff;background:#0d5abf;color:#fff;font-weight:800}.secondary{border-color:#294b72;background:transparent;color:#b9c8de}span{color:#ff8f96;font-size:13px}
</style>
