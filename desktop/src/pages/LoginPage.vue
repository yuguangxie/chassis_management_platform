<template>
  <main class="auth-page">
    <section class="auth-card">
      <div class="mark"><ShieldCheck :size="34" /></div>
      <h1>{{ bootstrapRequired ? '首次管理员初始化' : '工位登录' }}</h1>
      <p class="subtitle">低速无人车线控底盘生产下线管理平台</p>
      <p v-if="expired" class="notice">会话已过期或被撤销，请重新登录。</p>
      <p v-if="bootstrapRequired" class="notice warning">
        从本机受保护数据目录读取一次性初始化凭据；初始化成功后该凭据立即失效。
      </p>
      <form @submit.prevent="submit">
        <label v-if="bootstrapRequired">
          <span>一次性初始化凭据</span>
          <input v-model="bootstrapSecret" type="password" autocomplete="off" required minlength="20" />
        </label>
        <label><span>用户名</span><input v-model.trim="username" autocomplete="username" required minlength="3" /></label>
        <label><span>密码</span><input v-model="password" type="password" :autocomplete="bootstrapRequired ? 'new-password' : 'current-password'" required minlength="12" /></label>
        <label v-if="bootstrapRequired"><span>确认密码</span><input v-model="confirmation" type="password" autocomplete="new-password" required minlength="12" /></label>
        <p v-if="error" class="error">{{ error }}</p>
        <button class="primary" type="submit" :disabled="loading || checking">
          {{ loading ? '处理中…' : bootstrapRequired ? '初始化并登录' : '登录' }}
        </button>
      </form>
      <small>会话凭据仅保存在当前渲染进程的 sessionStorage；退出、锁屏、过期或撤销后立即清除。</small>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ShieldCheck } from 'lucide-vue-next'
import { formatApiError } from '../api/http'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const username = ref('')
const password = ref('')
const confirmation = ref('')
const bootstrapSecret = ref('')
const bootstrapRequired = ref(false)
const checking = ref(true)
const loading = ref(false)
const error = ref('')
const expired = computed(() => route.query.reason === 'expired')

onMounted(async () => {
  try {
    bootstrapRequired.value = (await auth.bootstrapStatus()).required
  } catch (cause) {
    error.value = formatApiError(cause)
  } finally {
    checking.value = false
  }
})

async function submit() {
  error.value = ''
  if (bootstrapRequired.value && password.value !== confirmation.value) {
    error.value = '两次输入的密码不一致'
    return
  }
  loading.value = true
  try {
    if (bootstrapRequired.value) await auth.bootstrap(bootstrapSecret.value, username.value, password.value)
    else await auth.login(username.value, password.value)
    const requested = typeof route.query.redirect === 'string' && route.query.redirect.startsWith('/')
      ? route.query.redirect
      : '/overview'
    await router.replace(requested)
  } catch (cause) {
    error.value = formatApiError(cause)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page{width:100vw;height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 50% 0,rgba(47,128,255,.22),transparent 38%),#07111f;color:#eaf2ff}.auth-card{width:min(440px,calc(100vw - 32px));padding:34px;border:1px solid #1e3a5f;border-radius:12px;background:linear-gradient(145deg,rgba(16,36,61,.98),rgba(7,17,31,.99));box-shadow:0 24px 70px rgba(0,0,0,.42)}.mark{width:58px;height:58px;display:grid;place-items:center;margin:0 auto 18px;border:1px solid #2f80ff;border-radius:12px;color:#8fc4ff;background:rgba(47,128,255,.12)}h1,p{margin:0;text-align:center}h1{font-size:24px}.subtitle{margin-top:8px;color:#8fa5c4}.notice{margin-top:18px;padding:10px;border:1px solid rgba(47,128,255,.45);border-radius:6px;color:#a9d1ff;background:rgba(47,128,255,.08);font-size:13px}.notice.warning{border-color:rgba(246,195,67,.48);color:#f6c343;background:rgba(246,195,67,.07)}form{display:grid;gap:14px;margin-top:22px}label{display:grid;gap:7px;color:#b9c8de;font-size:13px}input{height:40px;padding:0 12px;border:1px solid #294b72;border-radius:6px;background:#09182b;color:#fff;outline:none}input:focus{border-color:#2f80ff}.primary{height:42px;border:1px solid #4b98ff;border-radius:6px;background:linear-gradient(180deg,#176fdc,#0c4eaa);color:#fff;font-weight:800}.primary:disabled{opacity:.55}.error{color:#ff8f96;text-align:left;font-size:13px}small{display:block;margin-top:18px;color:#7188a8;line-height:1.5;text-align:center}
</style>
