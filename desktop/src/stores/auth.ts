import { defineStore } from 'pinia'
import { apiGet, apiPost, getApiToken, setApiToken } from '../api/http'
import { wsClient } from '../api/websocket'

export type Role = 'viewer' | 'operator' | 'engineer' | 'admin'

export interface Principal {
  username: string
  role: Role
  session_id: string
  expires_at: string | null
  permissions: string[]
}

interface SessionResponse extends Principal {
  token: string
  token_type: 'Bearer'
}

interface BootstrapStatus {
  required: boolean
  method: string
}

const ROLE_LEVEL: Record<Role, number> = { viewer: 10, operator: 20, engineer: 30, admin: 40 }
const LOCKED_USER_KEY = 'chassis_locked_username'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    principal: null as Principal | null,
    initialized: false,
    loading: false,
    expired: false,
    lockedUsername: window.sessionStorage.getItem(LOCKED_USER_KEY) || '',
  }),
  getters: {
    authenticated: (state) => Boolean(
      state.principal
      && getApiToken()
      && (!state.principal.expires_at || Date.parse(state.principal.expires_at) > Date.now()),
    ),
    isAdmin: (state) => state.principal?.role === 'admin',
  },
  actions: {
    async initialize() {
      if (this.initialized) return
      const token = getApiToken()
      if (!token) {
        this.initialized = true
        return
      }
      this.loading = true
      try {
        this.principal = await apiGet<Principal>('/auth/me')
        this.expired = false
      } catch {
        this.principal = null
        setApiToken('')
      } finally {
        this.loading = false
        this.initialized = true
      }
    },
    async bootstrapStatus(): Promise<BootstrapStatus> {
      return await apiGet<BootstrapStatus>('/auth/bootstrap/status')
    },
    async login(username: string, password: string) {
      const session = await apiPost<SessionResponse>('/auth/login', { username, password })
      this.acceptSession(session)
    },
    async bootstrap(bootstrapSecret: string, username: string, password: string) {
      const session = await apiPost<SessionResponse>('/auth/bootstrap', {
        bootstrap_secret: bootstrapSecret,
        username,
        password,
      })
      this.acceptSession(session)
    },
    async unlock(username: string, password: string) {
      const session = await apiPost<SessionResponse>('/auth/unlock', { username, password })
      this.acceptSession(session)
    },
    async lock() {
      const username = this.principal?.username || ''
      await apiPost<void>('/auth/lock')
      this.clearSession(false)
      this.lockedUsername = username
      window.sessionStorage.setItem(LOCKED_USER_KEY, username)
    },
    async logout() {
      try {
        await apiPost<void>('/auth/logout')
      } finally {
        this.clearSession(true)
      }
    },
    handleExpired() {
      this.expired = true
      this.clearSession(false)
    },
    can(minimum: Role): boolean {
      return Boolean(this.principal && ROLE_LEVEL[this.principal.role] >= ROLE_LEVEL[minimum])
    },
    hasAnyRole(roles: Role[]): boolean {
      return Boolean(this.principal && roles.includes(this.principal.role))
    },
    acceptSession(session: SessionResponse) {
      setApiToken(session.token)
      const { token: _token, token_type: _tokenType, ...principal } = session
      this.principal = principal
      this.initialized = true
      this.expired = false
      this.lockedUsername = ''
      window.sessionStorage.removeItem(LOCKED_USER_KEY)
      wsClient.resumeAfterAuth()
    },
    clearSession(clearLockedUser: boolean) {
      setApiToken('')
      this.principal = null
      wsClient.suspendForAuth()
      if (clearLockedUser) {
        this.lockedUsername = ''
        window.sessionStorage.removeItem(LOCKED_USER_KEY)
      }
    },
  },
})
