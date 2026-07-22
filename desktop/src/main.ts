import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { AUTH_EXPIRED_EVENT } from './api/http'
import { useAuthStore } from './stores/auth'
import './styles/tokens.css'
import './styles/global.css'
import './styles/industrial-theme.css'

const pinia = createPinia()
const application = createApp(App).use(pinia).use(router)
const auth = useAuthStore(pinia)
window.addEventListener(AUTH_EXPIRED_EVENT, () => {
  auth.handleExpired()
  if (router.currentRoute.value.path !== '/login') {
    void router.replace({ path: '/login', query: { reason: 'expired', redirect: router.currentRoute.value.fullPath } })
  }
})
void router.isReady().then(() => application.mount('#app'))
