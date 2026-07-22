import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getApiToken, setApiToken } from '../api/http'
import { useAuthStore, type Role } from './auth'

function principal(role: Role) {
  return {
    username:`${role}-user`, role, session_id:`session-${role}`,
    expires_at:new Date(Date.now()+60_000).toISOString(), permissions:[],
  }
}

describe('short session store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('stores a login token only in session storage and restores /me after refresh', async () => {
    const response = { ...principal('operator'), token:'runtime-short-session', token_type:'Bearer' }
    vi.stubGlobal('fetch', vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(response), { status:200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(principal('operator')), { status:200 })))
    const auth = useAuthStore()
    await auth.login('operator-user', 'Password-Only-In-Test-9!')
    expect(getApiToken()).toBe('runtime-short-session')
    expect(localStorage.getItem('chassis_api_token')).toBeNull()

    setActivePinia(createPinia())
    const refreshed = useAuthStore()
    await refreshed.initialize()
    expect(refreshed.principal?.role).toBe('operator')
    expect(refreshed.authenticated).toBe(true)
  })

  it('clears a rejected restored session', async () => {
    setApiToken('expired-session')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ code:'SESSION_EXPIRED', message:'expired' }), { status:401 })))
    const auth = useAuthStore()
    await auth.initialize()
    expect(auth.principal).toBeNull()
    expect(getApiToken()).toBe('')
  })

  it.each([
    ['viewer', false, false, false],
    ['operator', true, false, false],
    ['engineer', true, true, false],
    ['admin', true, true, true],
  ] as Array<[Role, boolean, boolean, boolean]>)('applies the %s button capability hierarchy', (role, operator, engineer, admin) => {
    const auth = useAuthStore()
    setApiToken(`short-${role}`)
    auth.principal = principal(role)
    expect(auth.can('operator')).toBe(operator)
    expect(auth.can('engineer')).toBe(engineer)
    expect(auth.isAdmin).toBe(admin)
  })
})
