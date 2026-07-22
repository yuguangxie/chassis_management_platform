import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory } from 'vue-router'
import { beforeEach, describe, expect, it } from 'vitest'
import { setApiToken } from '../api/http'
import { useAuthStore, type Role } from '../stores/auth'
import { createAppRouter, routes } from './index'

function authenticate(role: Role) {
  const auth = useAuthStore()
  setApiToken(`ephemeral-${role}`)
  auth.initialized = true
  auth.principal = {
    username: `${role}01`, role, session_id: `session-${role}`,
    expires_at: new Date(Date.now() + 60_000).toISOString(), permissions: [],
  }
}

describe('authenticated application routes', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
  })

  it('keeps eleven operational pages plus login, lock and 403 lazy-loaded', () => {
    const operational = routes.filter((route) => route.meta?.requiresAuth)
    expect(operational).toHaveLength(11)
    expect(operational.every((route) => typeof route.component === 'function')).toBe(true)
  })

  it('redirects unauthenticated direct access to login', async () => {
    const router = createAppRouter(createMemoryHistory())
    await router.push('/overview')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })

  it.each([
    ['viewer', '/overview', '/overview'],
    ['viewer', '/auto-test', '/forbidden'],
    ['operator', '/auto-test', '/auto-test'],
    ['operator', '/manual-control', '/forbidden'],
    ['engineer', '/manual-control', '/manual-control'],
    ['engineer', '/system-settings', '/system-settings'],
    ['admin', '/network-config', '/network-config'],
  ] as Array<[Role, string, string]>)('enforces %s route matrix for %s', async (role, target, expected) => {
    authenticate(role)
    const router = createAppRouter(createMemoryHistory())
    await router.push(target)
    await router.isReady()
    expect(router.currentRoute.value.path).toBe(expected)
  }, 15_000)

  it('rejects an expired principal even when a token remains in session storage', async () => {
    authenticate('engineer')
    const auth = useAuthStore()
    if (auth.principal) auth.principal.expires_at = new Date(Date.now() - 1_000).toISOString()
    const router = createAppRouter(createMemoryHistory())
    await router.push('/manual-control')
    await router.isReady()
    expect(router.currentRoute.value.path).toBe('/login')
  })
})
