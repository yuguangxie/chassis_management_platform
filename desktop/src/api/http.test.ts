import { beforeEach, describe, expect, it, vi } from 'vitest'
import { apiGet, AUTH_EXPIRED_EVENT, getApiToken, setApiToken } from './http'

describe('401 session race handling', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  it('does not let an old unauthenticated request clear a newly issued session', async () => {
    let release: (response:Response)=>void = () => undefined
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { release=resolve })))
    const pending = apiGet('/overview/summary')
    setApiToken('new-short-session')
    release(new Response(JSON.stringify({ code:'AUTH_REQUIRED', message:'required' }), { status:401 }))
    await expect(pending).rejects.toThrow('required')
    expect(getApiToken()).toBe('new-short-session')
  })

  it('does not let a superseded token response revoke its replacement', async () => {
    setApiToken('old-session')
    let release: (response:Response)=>void = () => undefined
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>((resolve) => { release=resolve })))
    const pending = apiGet('/auth/me')
    setApiToken('replacement-session')
    release(new Response(JSON.stringify({ code:'SESSION_REVOKED', message:'revoked' }), { status:401 }))
    await expect(pending).rejects.toThrow('revoked')
    expect(getApiToken()).toBe('replacement-session')
  })

  it('clears the current rejected session and emits expiration once', async () => {
    setApiToken('current-session')
    const expired = vi.fn()
    window.addEventListener(AUTH_EXPIRED_EVENT, expired)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ code:'SESSION_EXPIRED', message:'expired' }), { status:401 })))
    await expect(apiGet('/auth/me')).rejects.toThrow('expired')
    expect(getApiToken()).toBe('')
    expect(expired).toHaveBeenCalledTimes(1)
    window.removeEventListener(AUTH_EXPIRED_EVENT, expired)
  })
})
